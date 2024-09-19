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
from typing import Union

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


def create_config(
    repo_folder: Union[Path, str], session_folder: Union[Path, str], ks4: bool = False
):
    """
    Copies a configuration template file from the repository folder to the session folder.

    This function ensures that both `repo_folder` and `session_folder` are Path objects.
    It then copies the "config_template_emu.yaml" or "config_template_ks4.yaml" file from the `repo_folder` to the `session_folder`
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

    if ks4:
        sort_type_str = "ks4"
    else:
        sort_type_str = "emu"

    shutil.copyfile(
        repo_folder / "configs" / f"config_template_{sort_type_str}.yaml",
        session_folder / f"{sort_type_str}_config.yaml",
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


def load_ephys_data(
    config: dict,
) -> si.ChannelSliceRecording:
    """
    Loads electrophysiological data from the specified session folder and selects the specified channels.

    Parameters:
    - session_folder: Union[Path, str] - The path to the session folder containing the electrophysiological data.
    - channels: Union[List[int], np.ndarray] - A list or NumPy array containing the indices of the channels to select.

    Returns:
    - si.ChannelSliceRecording: A ChannelSliceRecording object containing the selected channels.
    """
    session_folder = config["Data"]["session_folder"]
    dataset_type = config["Data"]["dataset_type"]
    if dataset_type == "openephys":
        # If loading Open Ephys data
        loaded_recording = se.read_openephys(
            session_folder,
            stream_id=str(config["Data"]["openephys_stream_id"]),
            block_index=config["Data"]["openephys_experiment_id"],
        )
    elif dataset_type == "intan":
        # get list of intan recordings
        rhd_and_rhs_files = [
            rhd_or_rhs
            for rhd_or_rhs in sorted(Path.iterdir(Path(session_folder)))
            if (".rhs" in rhd_or_rhs.name or ".rhd" in rhd_or_rhs.name)
        ]
        if config["Data"]["emg_recordings"][0] == "all":
            chosen_rhd_and_rhs_files = rhd_and_rhs_files
        else:
            chosen_rhd_and_rhs_files = [
                rhd_and_rhs_files[i] for i in config["Data"]["emg_recordings"]
            ]
        # If loading Intan data
        loaded_recording_list = []
        for iRec in chosen_rhd_and_rhs_files:
            loaded_recording_list.append(se.read_intan(str(iRec), stream_id="0"))
        loaded_recording = si.append_recordings(loaded_recording_list)
    elif dataset_type == "nwb":
        # get list of nwb recordings
        nwb_files = [
            nwb
            for nwb in sorted(Path.iterdir(Path(session_folder)))
            if ".nwb" in nwb.name
        ]
        if config["Data"]["emg_recordings"][0] == "all":
            chosen_nwb_files = nwb_files
        else:
            chosen_nwb_files = [nwb_files[i] for i in config["Data"]["emg_recordings"]]
        # If loading NWB data
        loaded_recording_list = []
        for iRec in chosen_nwb_files:
            loaded_recording_list.append(se.read_nwb(str(iRec)))
        loaded_recording = si.append_recordings(loaded_recording_list)
    elif dataset_type == "binary":
        # get list of binary recordings
        bin_or_dat_files = [
            bin_or_dat
            for bin_or_dat in sorted(Path.iterdir(Path(session_folder)))
            if (".bin" in bin_or_dat.name or ".dat" in bin_or_dat.name)
        ]
        if config["Data"]["emg_recordings"][0] == "all":
            chosen_bin_or_dat_files = bin_or_dat_files
        else:
            chosen_bin_or_dat_files = [
                bin_or_dat_files[i] for i in config["Data"]["emg_recordings"]
            ]
        # If loading binary data
        loaded_recording_list = []
        for iRec in chosen_bin_or_dat_files:
            loaded_recording_list.append(
                se.read_binary(
                    str(iRec),
                    sampling_frequency=config["Data"]["binary_sampling_rate"],
                    num_channels=config["Data"]["binary_num_channels"],
                    dtype=config["Data"]["binary_dtype"],
                )
            )
        loaded_recording = si.append_recordings(loaded_recording_list)

    return loaded_recording


def preprocess_ephys_data(
    recording_obj: si.ChannelSliceRecording, this_config: dict, iGroup: Union[int]
) -> Union[si.ChannelSliceRecording, si.FrameSliceRecording]:
    """
    Preprocesses the electrophysiological data based on the specified configuration.

    Parameters:
    - recording_obj: si.ChannelSliceRecording - The ChannelSliceRecording object containing the electrophysiological data.
    - config: dict - The configuration dictionary containing the preprocessing parameters.

    Returns:
    - si.ChannelSliceRecording: The preprocessed ChannelSliceRecording object.
    """
    time_range_is_disabled = (
        this_config["Data"]["time_range"][0] == 0
        and this_config["Data"]["time_range"][1] == 0
    )
    assert time_range_is_disabled or (
        this_config["Data"]["time_range"][0] < this_config["Data"]["time_range"][1]
    ), "First element of time_range must be less than the second element."

    # check which recordings to use and whether to call concatenate_emg_data
    if this_config["Data"]["emg_recordings"][0] == "all":
        emg_recordings_to_use = np.arange(recording_obj.get_num_segments())
    else:
        emg_recordings_to_use = np.array(this_config["Data"]["emg_recordings"])

    if len(emg_recordings_to_use) > 1 and not time_range_is_disabled:
        raise ValueError(
            "Time range must be disabled if concatenating recordings (i.e., time_range: [0, 0])."
        )
    # concatenate the recordings if it's the first sort group, otherwise simply load it from last iteration
    if len(emg_recordings_to_use) > 1 and iGroup == 0:
        loaded_recording = concatenate_emg_data(
            this_config["Data"]["session_folder"],
            emg_recordings_to_use,
            recording_obj,
            this_config,
        )
    elif len(emg_recordings_to_use) > 1 and iGroup > 0:
        concat_data_path = this_config["Data"]["session_folder"] / "concatenated_data"
        loaded_recording = si.load_extractor(concat_data_path)
    else:
        loaded_recording = recording_obj.select_segments(emg_recordings_to_use)

    # check for [all] in emg_chan_list
    if this_config["Group"]["emg_chan_list"][iGroup][0] == "all":
        this_config["Group"]["emg_chan_list"][iGroup] = np.arange(
            loaded_recording.get_num_channels()
        ).tolist()
    # remove any ADC channels from the list
    this_config["Group"]["emg_chan_list"][iGroup] = [
        chan_idx
        for chan_idx in this_config["Group"]["emg_chan_list"][iGroup]
        if "ADC" not in loaded_recording.get_channel_ids()[chan_idx]
    ]
    # slice channels for this group
    selected_channel_ids = loaded_recording.get_channel_ids()[
        this_config["Group"]["emg_chan_list"][iGroup]
    ]
    # Slice the recording to include only the specified channels
    sliced_recording = loaded_recording.channel_slice(selected_channel_ids)
    if not time_range_is_disabled:
        # Slice the recording to include only the specified time range
        sliced_recording = sliced_recording.frame_slice(
            start_frame=int(
                round(
                    this_config["Data"]["time_range"][0]
                    * loaded_recording.get_sampling_frequency()
                )
            ),
            end_frame=int(
                round(
                    this_config["Data"]["time_range"][1]
                    * loaded_recording.get_sampling_frequency()
                )
            ),
        )

    # Apply bandpass filter to the EMG data
    recording_filtered = spre.bandpass_filter(
        sliced_recording,
        freq_min=this_config["Data"]["emg_passband"][0],
        freq_max=this_config["Data"]["emg_passband"][1],
    )
    remove_bad_emg_chans = this_config["Group"]["remove_bad_emg_chans"][iGroup]
    # detect bad channels on filtered recording
    if isinstance(remove_bad_emg_chans, bool):
        bad_channel_ids, _ = spre.detect_bad_channels(recording_filtered, method="mad")
    elif isinstance(remove_bad_emg_chans, str):
        probe = create_probe(recording_filtered)
        recording_filtered = recording_filtered.set_probe(probe)
        # input can be either "mad" or "coherence+psd", but users may input mad# where # is a number
        # setting the threshold
        numeric_idxs = np.nonzero([i.isdigit() for i in remove_bad_emg_chans])[0]
        num_digits = len(numeric_idxs)
        if num_digits > 0:
            if num_digits > 1:
                assert (
                    np.diff(numeric_idxs).all() == 1
                ), f"Invalid input for remove_bad_emg_chans: {remove_bad_emg_chans}. If using a threshold, it must be a number after the method string."
            method_str = remove_bad_emg_chans[: numeric_idxs[0]]
            assert (
                method_str != "coherence+psd"
            ), f'Invalid input for remove_bad_emg_chans: {remove_bad_emg_chans}. "coherence+psd" method does not take a threshold value.'
            threshold = int(remove_bad_emg_chans[numeric_idxs[0] :])
        else:
            method_str = remove_bad_emg_chans
            threshold = 5
        if method_str not in ["coherence+psd", "std", "mad"]:
            raise ValueError(
                f'remove_bad_emg_chans method string must be either "coherence+psd", "std", "mad", "std#", or "mad#" where # is a number to set the threshold, but got "{remove_bad_emg_chans}".'
            )
        bad_channel_ids, _ = spre.detect_bad_channels(
            recording_filtered, method=method_str, std_mad_threshold=threshold
        )
    elif isinstance(remove_bad_emg_chans, (list, np.ndarray)):
        raise TypeError(
            f'Elements of this_config["Group"]["remove_bad_emg_chans"] type should either be bool or str, but got {type(remove_bad_emg_chans)}.'
        )
    else:
        bad_channel_ids = None

    if bad_channel_ids is None and remove_bad_emg_chans == True:
        print("No bad channels detected.")
    elif remove_bad_emg_chans == False:
        print(
            f"Bad channels detected: {bad_channel_ids}, and none were removed because remove_bad_emg_chans is set to False."
        )
    else:
        print("Bad channels being removed:\n" + str(bad_channel_ids))
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
) -> Union[si.ChannelSliceRecording, se.OpenEphysBinaryRecordingExtractor]:
    """
    Concatenates the specified EMG recordings and saves the concatenated data to the session folder.
    Results are saved in the "concatenated_data" folder within the session folder. If the
    concatenated data already exists and the Data section of the configuration file has not changed,
    data will be loaded instead of recomputed.

    Parameters:
    - session_folder: Union[Path, str] - The path to the session folder containing the electrophysiological data.
    - emg_recordings: Union[list, np.ndarray] - A list or NumPy array containing the indices of the EMG recordings to concatenate.
    - recording_object: Union[si.ChannelSliceRecording, se.OpenEphysBinaryRecordingExtractor] - The ChannelSliceRecording or OpenEphysBinaryRecordingExtractor object containing the electrophysiological data.

    Returns:
    - Union[si.ChannelSliceRecording, se.OpenEphysBinaryRecordingExtractor]: The concatenated recording object.
    """

    def concat_and_save(concat_data_path: Path):
        try:
            rec_list = [recording_object.select_segments([i]) for i in emg_recordings]
        except AssertionError:
            rec_list = [
                recording_object.select_segments([i])
                for i in range(recording_object.get_num_segments())
            ]

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
            if not dicts_match(last_config_dict["Data"], this_config_dict["Data"]):
                print(
                    "Data section of configuration file has changed since last run, re-running concatenation..."
                )
                recording_concatenated = concat_and_save(concat_data_path)
                dump_yaml(concat_data_path.joinpath("last_config.yaml"), this_config)
            else:
                print(
                    "Data section of configuration file has not changed since last run, will load previous concatenated data..."
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


def extract_sorting_result(sorting, this_config, ii):
    """
    Parallel-friendly function to extract and save the sorting results to the specified folder.

    Parameters:
    - sorting: KiloSortSortingExtractor - The sorting extractor object containing the spike sorting results.
    - this_config: dict - The configuration dictionary containing the parameters for the sorting job.
    - ii: int - The index of the sorting job in the job list.

    Returns:
    - None
    """
    # Save sorting results by exporting to Phy format
    waveforms_folder = Path(this_config["Sorting"]["sorted_folder"]) / "waveforms"
    phy_folder = Path(this_config["Sorting"]["sorted_folder"]) / "phy"
    # get nt size from the sorting object, which is the width of the waveforms
    sampling_frequency = sorting.get_sampling_frequency()
    nt = this_config["KS"]["nt"]
    ms_buffer = nt / sampling_frequency * 1000 / 2
    print(
        f"Worker {ii} extracting waveforms with nt={nt} at fs={sampling_frequency} Hz (ms_before=ms_after={np.round(ms_buffer, 3)} ms)."
    )
    try:
        we = si.extract_waveforms(
            job_list[ii]["recording"],
            sorting,
            waveforms_folder,
            ms_before=ms_buffer,
            ms_after=ms_buffer,
            overwrite=True,
        )
    except ValueError as e:
        print("Error extracting waveforms:", e)
        import spikeinterface.curation as scur

        remove_excess_spikes_recording = scur.remove_excess_spikes(
            sorting, job_list[ii]["recording"]
        )

        # loaded_recording.set_probe(probe)
        we = si.extract_waveforms(
            remove_excess_spikes_recording, sorting, waveforms_folder, overwrite=True
        )

    export_to_phy(
        we,
        output_folder=phy_folder,
        compute_pc_features=False,
        copy_binary=True,
        use_relative_path=True,
        verbose=False,
    )

    # move all sorter_output files into sorted_folder, then delete it
    shutil.copytree(
        Path(this_config["Sorting"]["sorted_folder"]) / "sorter_output",
        Path(this_config["Sorting"]["sorted_folder"]),
        dirs_exist_ok=True,
    )
    shutil.rmtree(
        Path(this_config["Sorting"]["sorted_folder"]) / "sorter_output",
        ignore_errors=True,
    )

    # move all phy files into sorted_folder, overwriting any existing duplicate files, then delete it
    shutil.copytree(
        phy_folder,
        Path(this_config["Sorting"]["sorted_folder"]),
        dirs_exist_ok=True,
    )
    shutil.rmtree(phy_folder, ignore_errors=True)

    # move results into file folder for storage
    time_stamp_us = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    Th_this_config = (
        this_config["KS"]["Th_learned"],
        this_config["KS"]["Th_universal"],
        tuple(this_config["KS"]["Th_single_ch"]),
    )
    # if no gridsearch was done, do not use the params_suffix
    if this_config["Sorting"]["do_KS_param_gridsearch"] == 0:
        params_suffix = ""
    else:
        params_suffix = (
            f"Th_{Th_this_config[0]},{Th_this_config[1]}_spkTh_{Th_this_config[2]})"
        )
    # export the KS parameter keys that were gridsearched to the filename as Param1-Vals1_Param2-Vals2
    # params_suffix = "_".join(
    #     [
    #         f"{key}-{val}"
    #         for key, val in iParams[ii].items()
    #         if key in this_config["Sorting"]["gridsearch_KS_params"]
    #     ]
    # )
    final_filename = f'{str(Path(this_config["Sorting"]["sorted_folder"])).split("_wkr")[0]}_{params_suffix}'
    # insert the timestamp after sorted_
    final_filename = final_filename.replace("sorted_", f"sorted_{time_stamp_us}_")
    # if only 1 group, remove _g0 from the filename
    if len(this_config["Group"]["emg_chan_list"]) == 1:
        final_filename = final_filename.replace("_g0", "")
    # remove whitespace and parens from the filename
    final_filename = Path(final_filename)
    final_filename = final_filename.with_name(final_filename.name.replace(" ", ""))
    final_filename = final_filename.with_name(final_filename.name.replace("(", ""))
    final_filename = final_filename.with_name(final_filename.name.replace(")", ""))
    final_filename = str(final_filename)
    # remove any trailing comma or underscore from the filename
    while final_filename[-1] in [",", "_"]:
        final_filename = final_filename[:-1]

    # rename the folder to preserve the latest sorting results in the sorted_g#_wkr# folder
    # also make a new sorter_output_HHMMSSffffff folder with a timestamp
    shutil.move(this_config["Sorting"]["sorted_folder"], final_filename)
    # dump this_config into the final folder of each sort
    dump_yaml(Path(final_filename).joinpath("emu_config.yaml"), this_config)
    # save the this_config["emg_chans_used"] to a npy file in the final folder
    np.save(
        Path(final_filename).joinpath("emg_chans_used.npy"),
        this_config["emg_chans_used"],
    )
    # print for user to copy and paste into terminal if desired
    print(f"\nTo view in Phy, run:\nphy template-gui {final_filename}/params.py\n")


def run_KS_sorting(job_list, these_configs):
    """
    Run Kilosort4 spike sorting on the specified recordings and save the results.

    Parameters:
    - job_list: list - A list of dictionaries containing the job parameters for each sorting job.
    - these_configs: list - A list of dictionaries containing the configuration parameters for each sorting job.

    Returns:
    - None
    """
    ## job_list is of below structure:
    # job_list = [
    #     {
    #         "sorter_name": "kilosort4",
    #         "recording": recording_list[i],
    #         "output_folder": these_configs[i]["Sorting"]["sorted_folder"],
    #         **this_config["KS"],
    #     }

    # Run spike sorting
    sortings = ss.run_sorter_jobs(
        job_list=job_list,
        engine="joblib",
        engine_kwargs={"n_jobs": these_configs[0]["Sorting"]["num_KS_jobs"]},
        return_output=True,
    )

    # Now extract and write the sorting results to each sorted_folder
    if these_configs[0]["Sorting"]["num_KS_jobs"] > 1:
        try:
            # do this in parallel using Pool
            with Pool(these_configs[0]["Sorting"]["num_KS_jobs"]) as pool:
                pool.starmap(
                    extract_sorting_result,
                    zip(sortings, these_configs, range(len(job_list))),
                )
        except (
            NameError
        ):  # this is to catch a Windows error where these_configs is not defined in the worker
            for ii, sorting in enumerate(sortings):
                extract_sorting_result(sorting, these_configs[ii], ii)
    else:
        # only run one job, since num_KS_jobs is set to 1
        extract_sorting_result(sortings[0], these_configs[0], 0)


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
        help="Reset the configuration file to the default EMUsort template",
    )
    parser.add_argument(  # ability to reset the config file for KS4 default settings
        "--ks4-reset-config",
        action="store_true",
        help="Reset the configuration file to the default Kilosort4 template",
    )
    parser.add_argument(
        "-s", "--sort", action="store_true", help="Perform spike sorting"
    )
    # parser.add_argument(
    #     "-p",
    #     "--phy",
    #     action="store_true",
    #     help="Open Phy GUI for the specified folder datestring. Defaults to latest folder without datestring.",
    # )

    args = parser.parse_args()

    # Generate, reset, or load config file
    config_file_path = (
        Path(args.folder).expanduser().resolve().joinpath("emu_config.yaml")
    )
    # if the config doesn't exist or user wants to reset, load the config template
    if not config_file_path.exists() or args.reset_config or args.ks4_reset_config:
        print(f"Generating config file from default template: \n{config_file_path}\n")
        create_config(
            Path(__file__).parent,
            Path(args.folder).expanduser().resolve(),
            ks4=args.ks4_reset_config,
        )

    # open text editor to validate or edit the configuration file if desired
    if args.config:
        subprocess.run(["nano", config_file_path])

    # Load the configuration file
    yaml = YAML()
    full_config = yaml.load(config_file_path)

    # Prepare common configuration file, accounting for section titles, Data, Sorting, and Group
    full_config["Data"].update(
        {
            "repo_folder": Path(__file__).parent,
            "session_folder": Path(args.folder).expanduser().resolve(),
        }
    )

    if full_config["Sorting"]["num_KS_jobs"] > 1:
        print(
            "Because num_KS_jobs > 1, cannot use more than 1 core for spikeinterface global job kwargs. Setting n_jobs=1."
        )
        full_config["SI"]["n_jobs"] = 1

    si.set_global_job_kwargs(
        n_jobs=full_config["SI"]["n_jobs"],
        chunk_duration=full_config["SI"]["chunk_duration"],
    )

    # below are checks of the configuration file to avoid downstream errors
    assert full_config["KS"]["nblocks"] == False, "nblocks must be False for EMUsort"
    assert (
        full_config["KS"]["do_correction"] == False
    ), "do_correction must be False for EMUsort"
    # assert full_config["KS"]["do_CAR"] == False, "do_CAR must be False for EMUsort"

    # EMG Preprocessing and Spike Sorting
    if args.sort:

        # load data from the session folder
        recording = load_ephys_data(full_config)
        # Setting GPU ordering for parallel jobs to match nvidia-smi and nvitop
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        # ensure that the output folder is set to the session folder if not specified
        if full_config["Sorting"]["output_folder"] is None:
            full_config["Sorting"]["output_folder"] = Path(
                full_config["Data"]["session_folder"]
            )
        else:
            # ensure that the output folder is a valid path
            full_config["Sorting"]["output_folder"] = (
                Path(full_config["Sorting"]["output_folder"]).expanduser().resolve()
            )
            full_config["Sorting"]["output_folder"].mkdir(parents=True, exist_ok=True)

        # loop through each group of EMG channels to sort independently
        for iGroup, emg_chan_list in enumerate(full_config["Group"]["emg_chan_list"]):
            preproc_recording = preprocess_ephys_data(recording, full_config, iGroup)
            grp_zfill_amount = len(str(len(full_config["Group"]["emg_chan_list"])))
            this_group_sorted_folder = (
                Path(full_config["Sorting"]["output_folder"])
                / f'sorted_g{str(iGroup).zfill(grp_zfill_amount)}_{Path(full_config["Data"]["session_folder"]).name}'
            )
            print(f"Recording information: {preproc_recording}")
            # full_config["sort_group"] = iGroup
            iParams = list(
                ParameterGrid(full_config["Sorting"]["gridsearch_KS_params"])
            )  # get iterator of all possible param combinations
            if full_config["Sorting"]["do_KS_param_gridsearch"] == 0:
                # grab the first element of the ParameterGrid iterator, which is the default dictionary
                iParams = [iParams[0]]

            # create new folders if running in parallel
            total_KS_jobs = len(iParams)

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
            if full_config["Sorting"]["num_KS_jobs"] > 1:
                assert (
                    full_config["Sorting"]["do_KS_param_gridsearch"] == 1
                ), "Parallel jobs can only be used when do_KS_param_gridsearch is set to True"
            # create new folder for each parallel job to store results temporarily
            these_configs = []
            recording_list = []
            # loop through each parallel job and create separate config files for each
            for iW in worker_ids:
                # create new folder for each parallel job
                zfill_amount = len(str(full_config["Sorting"]["num_KS_jobs"]))
                tmp_sorted_folder = (
                    str(this_group_sorted_folder) + "_wkr" + str(iW).zfill(zfill_amount)
                )
                if Path(tmp_sorted_folder).exists():
                    shutil.rmtree(tmp_sorted_folder, ignore_errors=True)
                # Path(tmp_sorted_folder).mkdir(parents=True, exist_ok=True)
                recording_list.append(preproc_recording)
                # create a new config file for each parallel job
                this_config = deepcopy(full_config)
                this_config["Sorting"]["sorted_folder"] = tmp_sorted_folder
                # check for keys first
                if "Th" in iParams[iW]:
                    this_config["KS"]["Th_learned"] = iParams[iW]["Th"][0]
                    this_config["KS"]["Th_universal"] = iParams[iW]["Th"][1]
                if "spkTh" in iParams[iW]:
                    this_config["KS"]["Th_single_ch"] = iParams[iW]["spkTh"]
                this_config["num_chans"] = preproc_recording.get_num_channels()
                this_config["KS"]["nearest_chans"] = min(
                    this_config["num_chans"], this_config["KS"]["nearest_chans"]
                )  # do not let nearest_chans exceed the number of channels
                this_config["KS"]["nearest_templates"] = min(
                    this_config["num_chans"], this_config["KS"]["nearest_templates"]
                )  # do not let nearest_templates exceed the number of channels
                this_config["KS"]["torch_device"] = (
                    "cuda:" + torch_device_ids[iW] if is_available() else "cpu"
                )
                # store which channels were used for this group, minus 1 for 0-based indexing
                this_config["emg_chans_used"] = [
                    int(str(i).split("CH")[-1]) - 1
                    for i in preproc_recording.get_channel_ids()
                ]
                # print(this_config["KS"]["torch_device"])
                these_configs.append(this_config)

            job_list = [
                {
                    "sorter_name": "kilosort4",
                    "recording": recording_list[i],
                    "output_folder": these_configs[i]["Sorting"]["sorted_folder"],
                    **these_configs[i]["KS"],
                }
                for i in range(total_KS_jobs)
            ]
            run_KS_sorting(job_list, these_configs)

    # Print status and time elapsed
    print("Pipeline finished! You've earned a break.")
    finish_time = datetime.now()
    time_elapsed = finish_time - start_time
    print(
        f"Time elapsed: {strfdelta(time_elapsed, '{hours} hours, {minutes} minutes, {seconds} seconds')}"
    )

    # if args.phy:
    #     # make sure only one sort was performed
    #     if len(these_configs) > 1 or len(full_config["Group"]["emg_chan_list"]) > 1:
    #         print(
    #             "Multiple sorts were performed, ignoring -p/--phy flag. Phy command can only be used for one sort at a time."
    #         )
    #         args.phy = False

    #     if args.phy:
    #         # open Phy GUI for this final folder
    #         subprocess.run(
    #             ["phy", "template-gui", these_configs[0]["Data"]["final_folder"]]
    #         )
