import sys

if sys.version_info < (3, 5):
    sys.exit(
        "Error: Your Python version is not supported. Please use Python 3.5 or later."
    )

from datetime import datetime

start_time = datetime.now()  # include imports in time cost
import argparse
import os
import shutil
import subprocess
from copy import deepcopy

# from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Pool
from pathlib import Path
from pdb import set_trace
from typing import List, Union

import numpy as np
import spikeinterface as si
import spikeinterface.extractors as se
import spikeinterface.preprocessing as spre
import spikeinterface.sorters as ss
from probeinterface import Probe  # , get_probe
from ruamel.yaml import YAML
from sklearn.model_selection import ParameterGrid
from spikeinterface.exporters import export_to_phy
from torch.cuda import is_available

# import spikeinterface.comparison as sc
# import spikeinterface.curation as scur
# import spikeinterface.exporters as sexp
# import spikeinterface.postprocessing as spost
# import spikeinterface.qualitymetrics as sqm
# import spikeinterface.widgets as sw

# from probeinterface.plotting import plot_probe


def create_config(repo_folder: Union[Path, str], session_folder: Union[Path, str]):
    """
    Copies a configuration template file from the repository folder to the session folder.

    This function ensures that both `repo_folder` and `session_folder` are Path objects.
    It then copies the "emu_config_template.yaml" file from the `repo_folder` to the `session_folder`
    and renames it to "emu_config.yaml".

    Parameters:
    - repo_folder: Union[Path, str] - The path to the repository folder containing the configuration template.
    - session_folder: Union[Path, str] - The path to the session folder where the configuration file should be copied.
    """
    try:
        # Ensure both are Path objects
        repo_folder = Path(repo_folder)
        session_folder = Path(session_folder)
    except TypeError as e:
        raise TypeError("Please provide valid folder paths.") from e

    shutil.copyfile(
        repo_folder / "emu_config_template.yaml", session_folder / "emu_config.yaml"
    )


def create_probe(recording_obj):
    num_emg_chans = len(recording_obj.get_channel_ids())
    positions = np.zeros((num_emg_chans, 2))
    for i in range(num_emg_chans):
        x = 0
        y = i
        positions[i] = x, y
    positions[:, 1] *= -2

    probe = Probe(ndim=2, si_units="um")
    probe.set_contacts(positions=positions, shapes="square", shape_params={"width": 1})
    probe.device_channel_indices = np.arange(num_emg_chans)

    print(
        f"Probe created: {probe}, with {num_emg_chans} channels at positions: \n {positions}"
    )
    return probe


def strfdelta(tdelta: datetime, fmt: str) -> str:
    """
    Formats a timedelta object as a string based on the given format.

    This function converts a timedelta object into a string using a format string.
    The format string can include placeholders for days, hours, minutes, and seconds,
    which will be replaced by the corresponding values from the timedelta object.

    Parameters:
    - tdelta: timedelta - The timedelta object to format.
    - fmt: str - The format string. It can contain placeholders {days}, {hours}, {minutes}, and {seconds}.

    Returns:
    - str: The formatted string representing the timedelta.
    """
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)


def dump_yaml(dump_path: Path, this_config: dict):
    # convert Path objects to strings before saving
    this_config = path_to_str_recursive(this_config)
    with open(dump_path, "w") as f:
        yaml.dump(this_config, f)


def dicts_match(dict1, dict2):
    # Base case: if both inputs are not dictionaries, compare them directly
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        return dict1 == dict2

    # Sort items of both dictionaries
    sorted_items1 = sorted(dict1.items())
    sorted_items2 = sorted(dict2.items())
    # Check if the sorted items are equal
    if sorted_items1 != sorted_items2:
        return False

    # Recursively compare values if they are dictionaries
    for key, value in sorted_items1:
        if not dicts_match(value, dict2[key]):
            return False

    # If all checks pass, the dictionaries are equal
    return True


def path_to_str_recursive(data):
    if isinstance(data, Path):
        return str(data)
    elif isinstance(data, dict):
        return {key: path_to_str_recursive(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [path_to_str_recursive(item) for item in data]
    else:
        return data


def find(
    pattern: str, path: Union[Path, str], recursive: bool = True, exact: bool = False
) -> List[Path]:
    """
    Finds files matching a pattern in the specified path.

    Parameters:
    - pattern: str - The pattern to search for in filenames.
    - path: Union[Path, str] - The directory path to search in.
    - recursive: bool - If True, search recursively. If False, search only in the specified directory.
    - exact: bool - If True, match the exact pattern. If False, match any filenames containing the pattern.

    Returns:
    - List[Path]: A sorted list of Path objects matching the pattern.
    """
    try:
        path = Path(path)
    except TypeError:
        raise TypeError("The provided path must be a string or Path object")

    asterisk = "" if exact else "*"
    search_pattern = (
        f"**/{asterisk}{pattern}{asterisk}"
        if recursive
        else f"{asterisk}{pattern}{asterisk}"
    )

    return sorted(path.glob(search_pattern))


def load_ephys_data(
    session_folder: Union[Path, str], channels: Union[List[int], np.ndarray]
) -> si.ChannelSliceRecording:
    """
    Loads electrophysiological data from the specified session folder and selects the specified channels.

    Parameters:
    - session_folder: Union[Path, str] - The path to the session folder containing the electrophysiological data.
    - channels: Union[List[int], np.ndarray] - A list or NumPy array containing the indices of the channels to select.

    Returns:
    - si.ChannelSliceRecording: A ChannelSliceRecording object containing the selected channels.
    """
    # TODO, check if the data is in Open Ephys format or other formats
    # If loading Open Ephys data
    loaded_recording = se.read_openephys(session_folder)
    # Extract the channel IDs corresponding to the specified indices
    selected_channel_ids = loaded_recording.get_channel_ids()[channels]
    # Slice the recording to include only the specified channels
    loaded_recording = loaded_recording.channel_slice(selected_channel_ids)
    # # set a probe for the recording
    # probe = create_probe(loaded_recording)
    # loaded_recording.set_probe(probe)
    # loaded_recording.set_channel_locations(probe.contact_positions)

    return loaded_recording


def preprocess_ephys_data(
    recording_obj: si.ChannelSliceRecording, this_config: dict
) -> si.ChannelSliceRecording:
    """
    Preprocesses the electrophysiological data based on the specified configuration.

    Parameters:
    - recording_obj: si.ChannelSliceRecording - The ChannelSliceRecording object containing the electrophysiological data.
    - config: dict - The configuration dictionary containing the preprocessing parameters.

    Returns:
    - si.ChannelSliceRecording: The preprocessed ChannelSliceRecording object.
    """
    # check which recordings to use and whether to call concatenate_emg_data
    if this_config["Data"]["emg_recordings"][0] == "all":
        emg_recordings_to_use = np.arange(recording_obj.get_num_segments())
    else:
        emg_recordings_to_use = np.array(this_config["Data"]["emg_recordings"])
    if len(emg_recordings_to_use) > 1:
        loaded_recording = concatenate_emg_data(
            this_config["Data"]["session_folder"],
            emg_recordings_to_use,
            recording_obj,
            this_config,
        )
    else:
        loaded_recording = recording_obj.select_segments(emg_recordings_to_use)

    # Apply bandpass filter to the EMG data
    recording_filtered = spre.bandpass_filter(
        loaded_recording,
        freq_min=this_config["Data"]["emg_passband"][0],
        freq_max=this_config["Data"]["emg_passband"][1],
    )
    remove_bad_emg_chans = this_config["Group"]["remove_bad_emg_chans"][0]
    # detect bad channels on filtered recording
    if isinstance(remove_bad_emg_chans, bool):
        bad_channel_ids, _ = spre.detect_bad_channels(recording_filtered, method="mad")
    elif isinstance(remove_bad_emg_chans, str):
        bad_channel_ids, _ = spre.detect_bad_channels(
            recording_filtered, method=remove_bad_emg_chans
        )
    elif isinstance(remove_bad_emg_chans, (list, np.ndarray)):
        bad_channel_ids = remove_bad_emg_chans
    else:
        bad_channel_ids = None

    if bad_channel_ids is None and remove_bad_emg_chans == True:
        print("No bad channels detected.")
    elif remove_bad_emg_chans == False:
        print(
            f"Bad channels detected: {bad_channel_ids}, and none were removed because remove_bad_emg_chans is set to False."
        )
    else:
        print("Bad Channels:\n" + str(bad_channel_ids))
        recording_filtered = recording_filtered.channel_slice(
            np.setdiff1d(recording_filtered.get_channel_ids(), bad_channel_ids)
        )
        # recording_filtered = recording_filtered.remove_channels(bad_channel_ids)
    # # Apply common reference to the EMG data
    # recording_filtered = spre.common_reference(recording_filtered)
    # Apply notch filter to the EMG data
    recording_notch = spre.notch_filter(
        recording_filtered, freq=60, q=30
    )  # Apply notch filter at 60 Hz

    # set a probe for the recording
    probe = create_probe(recording_notch)
    preprocessed_recording = recording_notch.set_probe(probe)
    # align channels to maximize the correlation between channels
    # recording_notch = spre.align_snippets(recording_notch)

    return preprocessed_recording


def concatenate_emg_data(
    session_folder: Union[Path, str],
    emg_recordings: Union[list, np.ndarray],
    recording_object: Union[
        si.ChannelSliceRecording, se.OpenEphysBinaryRecordingExtractor
    ],
    this_config: dict,
) -> si.ChannelSliceRecording:

    def concat_and_save(concat_data_path: Path):
        rec_list = [recording_object.select_segments([i]) for i in emg_recordings]
        print(f"Selected {len(rec_list)} recordings for concatenation.")
        recording_concatenated = si.concatenate_recordings(rec_list)
        print("Concatenated recording:", recording_concatenated)
        recording_concatenated.save(
            format="binary", folder=concat_data_path, overwrite=True
        )
        return recording_concatenated

    session_folder = Path(session_folder)
    concat_data_path = session_folder / "concatenated_data"
    yaml = YAML()

    concat_exists = concat_data_path.exists()
    if concat_exists:
        last_config_file_exists = concat_data_path.joinpath("last_config.yaml").exists()
        if last_config_file_exists:
            with open(concat_data_path.joinpath("last_config.yaml")) as f:
                try:
                    last_config = yaml.load(f)
                    last_config_dict = dict(last_config)  # Cast to dictionary
                except TypeError as e:
                    print(
                        "Error loading previous configuration file 'last_config.yaml' or it is empty."
                    )
                    last_config_dict = {}
            this_config_dict = path_to_str_recursive(
                dict(this_config)
            )  # Cast to dictionary
            if not dicts_match(last_config_dict, this_config_dict):
                print(
                    "Configuration file has changed since last run, re-running concatenation..."
                )
                recording_concatenated = concat_and_save(concat_data_path)
                dump_yaml(concat_data_path.joinpath("last_config.yaml"), this_config)
            else:
                print(
                    "Configuration file has not changed since last run, will load previous concatenated data..."
                )
                try:
                    recording_concatenated = si.load_extractor(concat_data_path)
                    return recording_concatenated
                except:
                    print(
                        "Failed to load previously concatenated data, re-running concatenation..."
                    )
                    recording_concatenated = concat_and_save(concat_data_path)
        else:
            dump_yaml(concat_data_path.joinpath("last_config.yaml"), this_config)
    else:
        concat_data_path.mkdir(parents=True, exist_ok=True)
        print("Concatenated data folder created.")
        dump_yaml(concat_data_path.joinpath("last_config.yaml"), this_config)
        recording_concatenated = concat_and_save(concat_data_path)

    return recording_concatenated


def extract_sorting_result(sorting, ii):
    # Save sorting results by exporting to Phy format
    waveforms_folder = (
        Path(these_configs[ii]["Data"]["sorted_folder"]) / "sorter_output" / "waveforms"
    )
    phy_folder = (
        Path(these_configs[ii]["Data"]["sorted_folder"]) / "sorter_output" / "phy"
    )
    try:
        we = si.extract_waveforms(job_list[ii]["recording"], sorting, waveforms_folder)
    except ValueError as e:
        print("Error extracting waveforms:", e)
        import spikeinterface.curation as scur

        remove_excess_spikes_recording = scur.remove_excess_spikes(
            sorting, job_list[ii]["recording"]
        )

        # loaded_recording.set_probe(probe)
        we = si.extract_waveforms(
            remove_excess_spikes_recording, sorting, waveforms_folder
        )

    export_to_phy(
        we,
        output_folder=phy_folder,
        compute_pc_features=False,
        copy_binary=True,
        use_relative_path=True,
    )
    # move all phy files into sorter_output folder, overwriting existing files
    shutil.copytree(
        phy_folder,
        Path(these_configs[ii]["Data"]["sorted_folder"]) / "sorter_output",
        dirs_exist_ok=True,
    )
    shutil.rmtree(phy_folder, ignore_errors=True)

    # move results into file folder for storage
    time_stamp_us = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    Th_this_config = (
        these_configs[ii]["KS"]["Th_learned"],
        these_configs[ii]["KS"]["Th_universal"],
        tuple(these_configs[ii]["KS"]["Th_single_ch"]),
    )
    params_suffix = (
        f"Th_{Th_this_config[0]},{Th_this_config[1]}_spkTh_{Th_this_config[2]})"
    )
    # export the KS parameter keys that were gridsearched to the filename as Param1-Vals1_Param2-Vals2
    # params_suffix = "_".join(
    #     [
    #         f"{key}-{val}"
    #         for key, val in iParams[ii].items()
    #         if key in these_configs[ii]["Sorting"]["gridsearch_KS_params"]
    #     ]
    # )
    final_filename = f'{str(Path(these_configs[ii]["Data"]["sorted_folder"]).parent/"sorted")}_{time_stamp_us}_{params_suffix}'
    # remove whitespace and parens from the filename
    final_filename = final_filename.replace(" ", "")
    final_filename = final_filename.replace("(", "")
    final_filename = final_filename.replace(")", "")

    shutil.copytree(these_configs[ii]["Data"]["sorted_folder"], final_filename)
    # remove the temporary folder
    shutil.rmtree(these_configs[ii]["Data"]["sorted_folder"], ignore_errors=True)


def run_KS_sorting(job_list, these_configs):
    # job_list is of structure:
    # job_list = [
    #     {
    #         "sorter_name": "kilosort4",
    #         "recording": recording_list[i],
    #         "output_folder": these_configs[i]["Data"]["sorted_folder"],
    #         **this_config["KS"],
    # update the KS parameters in the config file using the iParams values

    # this_config["Group"]["emg_chan_list"] = np.arange(this_config["num_chans"])
    # loaded_recording.set_channel_locations(probe.contact_positions)

    # Run spike sorting
    sortings = ss.run_sorter_jobs(
        job_list=job_list,
        engine="joblib",
        engine_kwargs={"n_jobs": these_configs[0]["Sorting"]["num_KS_jobs"]},
        return_output=True,
    )
    # do this in parallel using Pool
    with Pool(these_configs[0]["Sorting"]["num_KS_jobs"]) as pool:
        pool.starmap(extract_sorting_result, zip(sortings, range(len(sortings))))
    # do not do in parallel, because extract_waveforms consumes all CPUs for a single job
    # for ii, sorting in enumerate(sortings):
    #     extract_sorting_result(sorting, ii)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process EMG data and perform spike sorting."
    )
    parser.add_argument(
        "-f", "--folder", help="Path to the session folder", required=True
    )
    parser.add_argument(
        "-c",
        "--config",
        action="store_true",
        help="Generate or update the configuration file",
    )
    parser.add_argument(  # ability to reset the config file
        "--reset-config",
        action="store_true",
        help="Reset the configuration file to the default template",
    )
    parser.add_argument(
        "-s", "--sort", action="store_true", help="Perform spike sorting"
    )

    args = parser.parse_args()

    yaml = YAML()
    # Generate, reset, or load config file
    try:
        if args.reset_config:
            print("Configuration file will be reset to default template.")
            create_config(Path(__file__).parent, Path(args.folder))
            raise FileNotFoundError
        # Load config file
        config_file_path = Path(args.folder).joinpath("emu_config.yaml")
        with open(config_file_path) as f:
            full_config = yaml.load(f)
    except FileNotFoundError as e:
        if not args.reset_config:
            print("WARNING: Configuration file not found, generating a new one...")
        # Generate or update the configuration file
        config_file_path = Path(args.folder).joinpath("emu_config.yaml")
        # if the config doesn't exist, load the config template from the repo folder and KS defaults
        if not config_file_path.exists():
            create_config(Path(__file__).parent, Path(args.folder))
            # insert the KS parameters into the config file, under the section "KS"
            with open(config_file_path, "r") as f:
                full_config = yaml.load(f)
                KS_config = (
                    ss.Kilosort4Sorter.default_params()
                )  # Load default KS parameters
                full_config["KS"] = (
                    KS_config  # insert the KS parameters into the config file
                )
            with open(config_file_path, "w") as f:
                yaml.dump(full_config, f)
            print(f"Configuration file saved at {config_file_path}")

    # open text editor to edit the configuration file if desired
    if args.config:
        subprocess.run(["nano", config_file_path])
    full_config = yaml.load(config_file_path)

    # Prepare common configuration file
    # full_config.update(
    #     {
    #         "GPU_to_use": np.array(full_config["Sorting"]["GPU_to_use"], dtype=int),
    #         "num_KS_jobs": int(full_config["Sorting"]["num_KS_jobs"]),
    #         "session_folder": Path(args.folder),
    #         "repo_folder": Path(__file__).parent,
    #         "emg_recordings": (
    #             np.array(full_config["Data"]["emg_recordings"], dtype=int)
    #             if type(full_config["Data"]["emg_recordings"][0]) != str
    #             else full_config["Data"]["emg_recordings"]
    #         ),
    #         "emg_passband": np.array(full_config["Data"]["emg_passband"], dtype=float),
    #         "emg_sampling_rate": float(full_config["Data"]["emg_sampling_rate"]),
    #         # "num_KS_components": int(full_config["Sorting"]["num_KS_components"]),
    #         "time_range": np.array(full_config["Data"]["time_range"], dtype=float),
    #         # "emg_analog_chan": int(full_config["Data"]["emg_analog_chan"]),
    #     }
    # )
    # Prepare common configuration file, accounting for section titles, Data, Sorting, and Group
    full_config["Data"].update(
        {
            "repo_folder": Path(__file__).parent,
            "session_folder": Path(args.folder),
            # "emg_recordings": (
            #     np.array(full_config["Data"]["emg_recordings"], dtype=int)
            #     if type(full_config["Data"]["emg_recordings"][0]) != str
            #     else full_config["Data"]["emg_recordings"]
            # ),
            # "emg_passband": np.array(full_config["Data"]["emg_passband"], dtype=float),
            # "emg_sampling_rate": float(full_config["Data"]["emg_sampling_rate"]),
            # "time_range": np.array(full_config["Data"]["time_range"], dtype=float),
        }
    )
    # full_config["Sorting"].update(
    #     {
    #         "GPU_to_use": np.array(full_config["Sorting"]["GPU_to_use"], dtype=int),
    #         "num_KS_jobs": int(full_config["Sorting"]["num_KS_jobs"]),
    #         "do_KS_param_gridsearch": int(full_config["Sorting"]["do_KS_param_gridsearch"]),
    #         "gridsearch_KS_params": full_config["Sorting"]["gridsearch_KS_params"],
    #     }
    # )
    # full_config["Group"].update(
    #     {
    #         "emg_chan_list": [
    #             np.array(chan_range, dtype=int)
    #             for chan_range in full_config["Group"]["emg_chan_list"]
    #         ],
    #         "remove_bad_emg_chans": [
    #             np.array(bad_chans, dtype=int)
    #             for bad_chans in full_config["Group"]["remove_bad_emg_chans"]
    #         ],
    #         "remove_chan_delays": [
    #             np.array(delays, dtype=int)
    #             for delays in full_config["Group"]["remove_chan_delays"]
    #         ],
    #     }
    # )

    # below are overrides to KS defaults which always improve performance with EMG data
    full_config["KS"].update(
        {
            "nblocks": int(0),
            "nearest_chans": len(full_config["Group"]["emg_chan_list"][0]),
            "do_correction": False,
        }
    )

    # EMG Preprocessing and Spike Sorting
    if args.sort:

        # load data from the session folder
        recording = load_ephys_data(
            full_config["Data"]["session_folder"],
            full_config["Group"]["emg_chan_list"][0],
        )
        # TODO: Preprocess EMG data
        recording = preprocess_ephys_data(recording, full_config)
        # update probe
        # probe = create_probe(recording)
        # recording.set_probe(probe)

        # Setting GPU Environment Variables
        # GPU_str = ",".join([str(i) for i in full_config["Sorting"]["GPU_to_use"]])
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        # os.environ["CUDA_VISIBLE_DEVICES"] = GPU_str
        full_config["Data"]["sorted_folder"] = (
            Path(full_config["Data"]["session_folder"]) / "sorted"
        )
        for iGroup in range(len(full_config["Group"]["emg_chan_list"])):
            print(f"Recording information: {recording}")
            full_config["sort_group"] = iGroup
            # full_config["emg_chan_map_file"] = (
            #     Path(full_config["Data"]["repo_folder"])
            #     / "channel_maps"
            #     / full_config["Group"]["emg_chan_map_file"][iGroup]
            # )
            full_config["num_chans"] = len(
                full_config["Group"]["emg_chan_list"][iGroup]
            )
            iParams = list(
                ParameterGrid(full_config["Sorting"]["gridsearch_KS_params"])
            )  # get iterator of all possible param combinations
            if full_config["Sorting"]["do_KS_param_gridsearch"] == 0:
                # grab the first element of the ParameterGrid iterator, which is the default dictionary
                iParams = [iParams[0]]

            # create new folders if running in parallel
            total_KS_jobs = len(iParams)
            # if full_config["Sorting"]["num_KS_jobs"] > 1:
            worker_ids = np.arange(total_KS_jobs)
            torch_device_ids = [
                str(
                    full_config["Sorting"]["GPU_to_use"][
                        j % len(full_config["Sorting"]["GPU_to_use"])
                    ]
                )
                for j in worker_ids
            ]
            # ensure proper configuration for parallel jobs
            # assert full_config["Sorting"]["num_KS_jobs"] <= len(
            #     full_config["Sorting"]["GPU_to_use"]
            # ), "Number of parallel jobs must be less than or equal to number of GPUs"
            if full_config["Sorting"]["num_KS_jobs"] > 1:
                assert (
                    full_config["Sorting"]["do_KS_param_gridsearch"] == 1
                ), "Parallel jobs can only be used when do_KS_param_gridsearch is set to True"
            # create new folder for each parallel job to store results temporarily
            these_configs = []
            recording_list = []
            for iW in worker_ids:
                # create new folder for each parallel job
                zfill_amount = len(str(full_config["Sorting"]["num_KS_jobs"]))
                tmp_sorted_folder = str(full_config["Data"]["sorted_folder"]) + str(
                    iW
                ).zfill(zfill_amount)
                if Path(tmp_sorted_folder).exists():
                    shutil.rmtree(tmp_sorted_folder, ignore_errors=True)
                # Path(tmp_sorted_folder).mkdir(parents=True, exist_ok=True)
                recording_list.append(recording)
                # create a new config file for each parallel job
                this_config = deepcopy(full_config)
                this_config["Data"]["sorted_folder"] = tmp_sorted_folder
                # check for keys first
                if "Th" in iParams[iW]:
                    this_config["KS"]["Th_learned"] = iParams[iW]["Th"][0]
                    this_config["KS"]["Th_universal"] = iParams[iW]["Th"][1]
                if "spkTh" in iParams[iW]:
                    this_config["KS"]["Th_single_ch"] = iParams[iW]["spkTh"]
                this_config["num_chans"] = recording.get_num_channels()
                this_config["KS"]["nearest_chans"] = this_config["num_chans"]
                this_config["KS"]["torch_device"] = (
                    "cuda:" + torch_device_ids[iW] if is_available() else "cpu"
                )
                # print(this_config["KS"]["torch_device"])
                these_configs.append(this_config)
            # create spikeinterface job_list similar to below example
            # here we run 2 sorters on 2 different recordings = 4 jobs
            # recording = ...
            # another_recording = ...
            # job_list = [
            #   {'sorter_name': 'tridesclous', 'recording': recording, 'output_folder': 'folder1','detect_threshold': 5.},
            #   {'sorter_name': 'tridesclous', 'recording': another_recording, 'output_folder': 'folder2', 'detect_threshold': 5.},
            #   {'sorter_name': 'herdingspikes', 'recording': recording, 'output_folder': 'folder3', 'clustering_bandwidth': 8., 'docker_image': True},
            #   {'sorter_name': 'herdingspikes', 'recording': another_recording, 'output_folder': 'folder4', 'clustering_bandwidth': 8., 'docker_image': True},
            # ]
            # # run in parallel according to the job_list
            # must split the job_list into smaller chunks divided by the number of parallel jobs
            # sortings = run_sorter_jobs(job_list=job_list, engine='joblib', engine_kwargs={'n_jobs': 2})

            job_list = [
                {
                    "sorter_name": "kilosort4",
                    "recording": recording_list[i],
                    "output_folder": these_configs[i]["Data"]["sorted_folder"],
                    **these_configs[i]["KS"],
                }
                for i in range(total_KS_jobs)
            ]

            # split job_list according to number of parallel jobs
            # job_list_split = np.array_split(
            #     job_list, full_config["Sorting"]["num_KS_jobs"]
            # )

            # split iParams according to number of parallel jobs
            # iParams_split = np.array_split(
            #     iParams, full_config["Sorting"]["num_KS_jobs"]
            # )
            # # run parallel jobs
            # with ProcessPoolExecutor() as executor:
            #     executor.map(
            #         run_KS_sorting,
            #         iParams_split,
            #         these_configs,
            #         [recording] * full_config["Sorting"]["num_KS_jobs"],
            #     )
            run_KS_sorting(job_list, these_configs)
            # else:
            # this_config = full_config.copy()
            # this_config["Data"]["sorted_folder"] = Path(
            #     str(full_config["Data"]["sorted_folder"]) + "0"
            # )
            # if Path(this_config["Data"]["sorted_folder"]).exists():
            #     shutil.rmtree(
            #         this_config["Data"]["sorted_folder"], ignore_errors=True
            #     )
            # shutil.copytree(
            #     full_config["Data"]["sorted_folder"], this_config["Data"]["sorted_folder"]
            # )
            # # check for keys first
            # if "Th" in iParams[0]:
            #     this_config["KS"]["Th_learned"] = iParams[0]["Th"][0]
            #     this_config["KS"]["Th_universal"] = iParams[0]["Th"][1]
            # if "spkTh" in iParams[0]:
            #     this_config["KS"]["Th_single_ch"] = iParams[0]["spkTh"]
            # this_config["num_chans"] = recording.get_num_channels()
            # this_config["KS"]["nearest_chans"] = this_config["num_chans"]
            # # Run spike sorting
            # job_list = [
            #     {
            #         "sorter_name": "kilosort4",
            #         "recording": recording,
            #         "output_folder": this_config["Data"]["sorted_folder"],
            #         **this_config["KS"],
            #     }
            # ]

    # Print status and time elapsed
    print("Pipeline finished! You've earned a break.")
    finish_time = datetime.now()
    time_elapsed = finish_time - start_time
    print(
        f"Time elapsed: {strfdelta(time_elapsed, '{hours} hours, {minutes} minutes, {seconds} seconds')}"
    )

    # Reset terminal mode
    subprocess.run(["stty", "sane"])
