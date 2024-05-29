from datetime import datetime

# start clock as soon as possible, before other imports
# calculate time taken to run each pipeline call
start_time = datetime.now()

import glob
import itertools
import os
import shutil
import subprocess
import sys
import tempfile
# import concurrent.futures
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from ruamel.yaml import YAML
from scipy.io import loadmat, savemat
from sklearn.model_selection import ParameterGrid

from sorting.Kilosort4.kilosort import run_kilosort


def read_file(file):
    with open(file, "rb") as f:
        return f.read()


def create_config(repo_folder, session_folder):
    shutil.copyfile(
        repo_folder + "/config_template.yaml", session_folder + "/config.yaml"
    )


def strfdelta(tdelta, fmt):
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)


def find(pattern, path, recursive=True, exact=False):
    if exact:
        asterisk = ""
    else:
        asterisk = "*"
    if recursive:
        result = sorted(Path(path).glob(f"**/{asterisk}{pattern}{asterisk}"))
    else:
        result = sorted(Path(path).glob(f"{asterisk}{pattern}{asterisk}"))
    return result


def concatenate_emg_data(open_ephys_data_folder, recordings_to_concatenate):
    def find_folders_with_prefix(folder, prefix):
        return [
            os.path.join(folder, subfolder)
            for subfolder in os.listdir(folder)
            if subfolder.startswith(prefix)
            and os.path.isdir(os.path.join(folder, subfolder))
        ]

    record_node_folders = find_folders_with_prefix(
        open_ephys_data_folder, "Record Node"
    )

    if len(record_node_folders) != 1:
        raise ValueError(
            "Expected one 'Record Node' folder, found:", len(record_node_folders)
        )

    record_node_folder = record_node_folders[0]
    experiment_folders = find_folders_with_prefix(record_node_folder, "experiment")

    if len(experiment_folders) != 1:
        raise ValueError(
            "Expected one 'experiment' folder, found:", len(experiment_folders)
        )

    experiment_folder = experiment_folders[0]
    recording_folders = [
        os.path.join(experiment_folder, recording_folder)
        for recording_folder in os.listdir(experiment_folder)
        if os.path.isdir(os.path.join(experiment_folder, recording_folder))
        and recording_folder not in [".", "..", "concatenated_data"]
    ]

    continuous_files = []
    for recording_folder in recording_folders:
        continuous_path_1 = os.path.join(
            recording_folder, "continuous", "Acquisition_Board-100.Rhythm Data"
        )
        continuous_path_2 = os.path.join(
            recording_folder, "continuous", "Rhythm_FPGA-100.0"
        )
        if os.path.isdir(continuous_path_1):
            continuous_files.append(os.path.join(continuous_path_1, "continuous.dat"))
        elif os.path.isdir(continuous_path_2):
            continuous_files.append(os.path.join(continuous_path_2, "continuous.dat"))
        else:
            raise FileNotFoundError(
                f"Neither folder {continuous_path_1} or {continuous_path_2} exists."
            )

    output_data = bytearray()

    for index in recordings_to_concatenate:
        found = False
        for recording_folder in recording_folders:
            trailing_digits = "".join(
                filter(str.isdigit, recording_folder.split(os.sep)[-1])
            )
            if str(index) == trailing_digits:
                found = True
                with open(
                    continuous_files[recording_folders.index(recording_folder)], "rb"
                ) as file:
                    print(
                        f"Reading {continuous_files[recording_folders.index(recording_folder)]}"
                    )
                    output_data += file.read()
                break
        if not found:
            raise ValueError(f"Recording {index} does not exist.")

    rhythm_folder_name = continuous_files[-1].split("/")[-2]
    concatenated_data_dir = os.path.join(
        experiment_folder,
        "concatenated_data",
        ",".join(map(str, recordings_to_concatenate)),
    )
    continuous_folder = os.path.join(
        concatenated_data_dir, "continuous", rhythm_folder_name
    )
    os.makedirs(continuous_folder, exist_ok=True)

    with open(os.path.join(continuous_folder, "continuous.dat"), "wb") as file:
        file.write(output_data)

    last_recording_folder = os.path.join(experiment_folder, recording_folders[-1])
    structure_oebin = os.path.join(last_recording_folder, "structure.oebin")
    if os.path.exists(structure_oebin):
        shutil.copy(structure_oebin, concatenated_data_dir)

    print(
        f"Data from {len(recordings_to_concatenate)} files concatenated together and saved in {continuous_folder}"
    )


def run_KS_sorting(iParams, worker_id, full_config, this_config):
    iParams = iter(iParams)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(
        full_config["Sorting"]["GPU_to_use"][worker_id]
    )
    save_path = (
        f"{this_config['sorted_folder']}{worker_id}"
        if full_config["Sorting"]["num_KS_jobs"] > 1
        else this_config["sorted_folder"]
    )
    print(
        f"Starting spike sorting of {save_path} on GPU {full_config['Sorting']['GPU_to_use'][worker_id]}"
    )
    worker_id = str(worker_id)
    with tempfile.TemporaryDirectory(suffix=f"_worker{worker_id}") as worker_folder:
        # loop until exhaustion of iterator
        while True:
            try:
                these_params = next(iParams)
                if (
                    type(these_params) == dict
                    and full_config["Sorting"]["do_KS_param_gridsearch"] == 1
                ):
                    print(
                        f"Using KS params from config['Sorting']['gridsearch_params'] for gridsearch:"
                    )
                    param_keys = list(these_params.keys())
                    param_keys_str = [f"'{k}'" for k in param_keys]
                    param_vals = list(these_params.values())
                    # each element of zipped_params is a tuple of key-value pairs
                    zipped_params = zip(param_keys_str, param_vals)
                    flattened_params = itertools.chain.from_iterable(zipped_params)
                    # this is a comma-separated string of key-value pairs
                    passable_params = ",".join(str(p) for p in flattened_params)
                # elif type(these_params) == str:
                else:
                    # print(f"Using KS params from Kilosort_run_myo_3.m for single job")
                    # passable_params = these_params  # this is a string: 'default'
                    print(
                        f"Using first elements of KS params from config['Sorting']['gridsearch_params'] for single job"
                    )
                    passable_params = "default"
                print(these_params)

                # else:
                #     print("ERROR: KS params must be a dictionary or a string.")
                #     raise TypeError
                # if config["Sorting"]["do_KS_param_gridsearch"] == 1:
                #     command_str = f"Kilosort_run_myo_3(struct({passable_params}),{worker_id},'{str(worker_folder)}');"
                # else:
                #     command_str = f"Kilosort_run_myo_3('{passable_params}',{worker_id},'{str(worker_folder)}');"
                # subprocess.run(
                #     [
                #         f"{matlab_root}",
                #         "-nosplash",
                #         "-nodesktop",
                #         "-r",
                #         (
                #             "rehash toolboxcache; restoredefaultpath;"
                #             f"addpath(genpath('{path_to_add}'));"
                #             f"{command_str}"
                #         ),
                #     ],
                #     check=True,
                # )
                run_kilosort(
                    settings=dict(
                        n_chan_bin=this_config["num_chans"],
                        nearest_chans=this_config["num_chans"],
                        batch_size=full_config["emg_sampling_rate"]
                        * full_config["Sorting"]["batch_size_seconds"],
                        nblocks=0,
                        Th_universal=these_params["Th"][0],
                        Th_learned=these_params["Th"][1],
                        Th_single_ch=these_params["spkTh"][0],
                        probe_path=this_config["emg_chan_map_file"],
                        n_pcs=this_config["num_KS_components"],
                    ),
                    filename=this_config["emg_binary_filename"],
                    results_dir=this_config["sorted_folder"],
                )
                try:
                    # extract waveforms for Phy FeatureView, skip if error
                    subprocess.run(
                        # "phy extract-waveforms params.py",
                        [
                            "phy",
                            "extract-waveforms",
                            "params.py",
                        ],
                        cwd=save_path,
                        check=True,
                    )
                except:
                    print("Error running 'phy extract-waveforms params.py', skipping.")

                # get number of good units and total number of clusters from rez.mat
                # rez = loadmat(f"{save_path}/rez.mat")
                # num_KS_clusters = str(len(rez["good"]))
                # sum the 1's in the good field of ops.mat to get number of good units
                # num_good_units = str(sum(rez["good"])[0])
                brokenChan = loadmat(f"{save_path}/brokenChan.mat")["brokenChan"]
                # goodChans = np.setdiff1d(np.arange(1, 17), brokenChan)
                # goodChans_str = ",".join(str(i) for i in goodChans)

                ## TEMP - remove this later: append git branch name to final_filename
                # get git branch name
                git_branches = subprocess.run(
                    ["git", "branch"], capture_output=True, text=True
                )
                git_branches = git_branches.stdout.split("\n")
                git_branches = [i.strip() for i in git_branches]
                git_branch = [i for i in git_branches if i.startswith("*")][0][2:]

                # remove spaces and single quoutes from passable_params string
                time_stamp_us = datetime.now().strftime("%Y%m%d_%H%M%S%f")
                filename_friendly_params = passable_params.replace("'", "").replace(
                    " ", ""
                )
                final_filename = (
                    f"sorted{str(worker_id)}"
                    f"_{time_stamp_us}"
                    f"_rec-{recordings_str}"
                    # f"_chans-{goodChans_str}"
                    # f"_{num_good_units}-good-of-{num_KS_clusters}-total"
                    f"_{filename_friendly_params}"
                    f"_{git_branch}"
                )
                # remove trailing underscore if present
                final_filename = (
                    final_filename[:-1]
                    if final_filename.endswith("_")
                    else final_filename
                )
                # store final_filename in a new ops.mat field in the sorted0 folder
                # ops = loadmat(f"{save_path}/ops.mat")
                # ops.update({"final_sorted_folder": final_filename})
                # savemat(f"{save_path}/ops.mat", ops)

                # for KS4, store final_filename in a new ops.npy field in the sorted0 folder
                ops = np.load(f"{save_path}/ops.npy", allow_pickle=True).item()
                ops.update({"final_sorted_folder": final_filename})
                np.save(f"{save_path}/ops.npy", ops)

                # copy sorted0 folder tree to a new folder with timestamp to label results by params
                # this serves as a backup of the sorted0 data, so it can be loaded into Phy later
                shutil.copytree(
                    save_path,
                    Path(save_path).parent.joinpath(final_filename),
                )

            except StopIteration:
                if full_config["Sorting"]["do_KS_param_gridsearch"] == 1:
                    print(f"Grid search complete for worker {worker_id}")
                return  # exit the function
            except:
                if full_config["Sorting"]["do_KS_param_gridsearch"] == 1:
                    print("Error in grid search.")
                else:
                    print("Error in sorting.")
                raise  # re-raise the exception


repo_folder = os.path.dirname(os.path.realpath(__file__))
opts = [opt for opt in sys.argv[1:] if opt.startswith("-")]
args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

# use -f option to specify project folder for this session
if "-f" in opts:
    session_folder = args[0]
    if os.path.isdir(session_folder):
        print("Using project folder " + session_folder)
    else:
        raise SystemExit(
            "Provided project folder path is not valid (you had one job...)"
        )
else:
    raise SystemExit(
        f"Usage: {sys.argv[0]} -f argument must be present. Also, ensure environment is activated."
    )

full_config = False
sort = False
post = False
plot = False
phy = False

if "-config" in opts:
    full_config = True
if "-sort" in opts:
    sort = True
if "-post" in opts:
    post = True
if "-plot" in opts:
    plot = True
if "-phy" in opts:
    phy = True
if "-full" in opts:
    sort = True
    post = True

# Search project folder for existing configuration file
config_file = find("config.yaml", session_folder, recursive=False, exact=True)
if len(config_file) > 1:
    raise SystemExit(
        "There shouldn't be more than one config file in here (something went wrong)"
    )
elif len(config_file) == 0:
    print("No config file found - creating one now")
    create_config(repo_folder, session_folder)
    config_file = find("config.yaml", session_folder, recursive=False, exact=True)
config_file = config_file[0]

if full_config:
    if os.name == "posix":  # detect Unix
        subprocess.run(f"nano {config_file}", shell=True, check=True)
        print("Configuration done.")
    elif os.name == "nt":  # detect Windows
        subprocess.run(f"notepad {config_file}", shell=True, check=True)
        print("Configuration done.")

# Load config
print("Using config file " + str(config_file))
# make round-trip loader
yaml = YAML()
with open(config_file) as f:
    full_config = yaml.load(f)

# Check config for missing information and attempt to auto-fill
full_config["session_folder"] = session_folder

temp_folder = glob.glob(session_folder + "/*_myo")
if len(temp_folder) > 1:
    SystemExit("There shouldn't be more than one Myomatrix folder")
elif len(temp_folder) == 0:
    print("No Myomatrix data in this recording session")
    full_config["working_folder"] = ""
else:
    if os.path.isdir(temp_folder[0]):
        full_config["working_folder"] = temp_folder[0]

# ensure global fields are present in config
if full_config["working_folder"] != "":
    print("Using emg data folder " + full_config["working_folder"])
if not "emg_recordings" in full_config:
    full_config["emg_recordings"] = [1]
if not "concatenate_recordings" in full_config:
    full_config["concatenate_recordings"] = False
if not "emg_passband" in full_config:
    full_config["emg_passband"] = [250, 5000]
if not "emg_sampling_rate" in full_config:
    full_config["emg_sampling_rate"] = 30000
# ensure Sorting fields are present in config
if not "batch_size_seconds" in full_config["Sorting"]:
    full_config["Sorting"]["batch_size_seconds"] = 2
if not "num_KS_components" in full_config["Sorting"]:
    full_config["Sorting"]["num_KS_components"] = 6
if not "GPU_to_use" in full_config["Sorting"]:
    full_config["Sorting"]["GPU_to_use"] = [0]
if not "num_KS_jobs" in full_config["Sorting"]:
    full_config["Sorting"]["num_KS_jobs"] = 1
if not "do_KS_param_gridsearch" in full_config["Sorting"]:
    full_config["Sorting"]["do_KS_param_gridsearch"] = False
if not "gridsearch_params" in full_config["Sorting"]:
    full_config["Sorting"]["gridsearch_params"] = dict(
        Th=[[9, 8], [10, 4], [7, 3], [5, 2], [2, 1]],
        spkTh=[[-6], [-3], [-9]],  # [-3, -6], [-6, -9]],
    )
# ensure Group fields are present in config
if not "emg_chan_map_file" in full_config["Group"]:
    full_config["emg_chan_map_file"] = [
        ["linear_16ch_RF400_kilosortChanMap_unitSpacing.mat"]
    ]
if not "emg_chan_list" in full_config["Group"]:
    full_config["Group"]["emg_chan_list"] = [[1, 16]]
if not "emg_muscle_list" in full_config["Group"]:
    full_config["Group"]["emg_muscle_list"] = [
        ["Muscle" + str(i) for i in range(len(full_config["Group"]["emg_chan_list"]))]
    ]
if not "remove_bad_emg_chans" in full_config["Group"]:
    full_config["Group"]["remove_bad_emg_chans"] = [False] * len(
        full_config["Group"]["emg_chan_list"]
    )
if not "remove_channel_delays" in full_config["Group"]:
    full_config["Group"]["remove_channel_delays"] = [False] * len(
        full_config["Group"]["emg_chan_list"]
    )
if not "emg_analog_chan" in full_config:
    full_config["emg_analog_chan"] = 17

# input assertions
assert (
    full_config["Sorting"]["num_KS_jobs"] >= 1
), "Number of parallel jobs must be greater than or equal to 1"
assert full_config["emg_recordings"][0] == "all" or all(
    [
        (item == round(item) >= 1 and isinstance(item, (int, float)))
        for item in full_config["emg_recordings"]
    ]
), "'emg_recordings' field must be a list of positive integers, or 'all' as first element"
assert all(
    [
        (item >= 0 and isinstance(item, int))
        for item in full_config["Sorting"]["GPU_to_use"]
    ]
), "'GPU_to_use' field must be greater than or equal to 0"
assert (
    full_config["Sorting"]["num_KS_components"] >= 1
), "Number of KS components must be greater than or equal to 1"
assert (
    full_config["emg_sampling_rate"] >= 1
), "Myomatrix sampling rate must be greater than or equal to 1"


# use -d option to specify which sort folder to post-process
if "-d" in opts:
    date_str = args[1]
    # make sure date_str is in the format YYYYMMDD_HHMMSS, YYYYMMDD_HHMMSSsss, or YYYYMMDD_HHMMSSffffff
    assert (
        (len(date_str) == 15 or len(date_str) == 18 or len(date_str) == 21)
        & date_str[:8].isnumeric()
        & date_str[9:].isnumeric()
        & (date_str[8] == "_")
    ), "Argument after '-d' must be a date string in format: YYYYMMDD_HHMMSS, YYYYMMDD_HHMMSSsss, or YYYYMMDD_HHMMSSffffff"
    # check if date_str is present in any of the subfolders in the config["working_folder"] path
    subfolder_list = os.listdir(full_config["working_folder"])
    previous_sort_folder_to_use = [
        iFolder for iFolder in subfolder_list if date_str in iFolder
    ]
    assert (
        len(previous_sort_folder_to_use) > 0
    ), f'No matching subfolder found in {full_config["working_folder"]} for the date string provided'
    assert (
        len(previous_sort_folder_to_use) < 2
    ), f'Multiple matching subfolders found in {full_config["working_folder"]} for the date string provided. Try using a more specific date string, like "YYYYMMDD_HHMMSSffffff"'
    previous_sort_folder_to_use = str(previous_sort_folder_to_use[0])
else:
    if full_config["Sorting"]["num_KS_jobs"] == 1:
        if "-phy" in opts or "-post" in opts:
            try:
                # previous_sort_folder_to_use = str(
                #     loadmat(f'{full_config["working_folder"]}/sorted0/ops.mat')[
                #         "final_sorted_folder"
                #     ][0]
                # )
                # for KS4, use ops.npy instead of ops.mat
                ops = np.load(
                    f'{full_config["working_folder"]}/sorted0/ops.npy',
                    allow_pickle=True,
                ).item()
                previous_sort_folder_to_use = ops["final_sorted_folder"]
            except FileNotFoundError:
                print(
                    "WARNING: No ops.npy file found in sorted0 folder, not able to detect previous sort folder.\n"
                    "         If using '-phy' or '-post', try using the '-d' flag to specify the datestring\n"
                )
            except KeyError:
                print(
                    "WARNING: No 'final_sorted_folder' field found in ops.npy file, not able to detect previous sort folder.\n"
                    "         If using '-phy' or '-post', try using the '-d' flag to specify the datestring\n"
                )
            except:
                raise
    else:
        if "-phy" in opts or "-post" in opts:
            raise SystemExit(
                "Cannot guess desired previous sort folder after parallel sorting. Please specify manually using the '-d' flag"
            )

# find MATLAB installation
if Path("/usr/local/bin/matlab").is_file():
    matlab_root = "/usr/local/bin/matlab"
elif Path("/usr/local/MATLAB/R2021a/bin/matlab").is_file():
    matlab_root = (
        "/usr/local/MATLAB/R2021a/bin/matlab"  # something else for testing locally
    )
elif Path("/srv/software/matlab/R2021b/bin/matlab").is_file():
    matlab_root = "/srv/software/matlab/R2021b/bin/matlab"
elif glob.glob("/usr/local/MATLAB/R*") != []:
    matlab_path = glob.glob("/usr/local/MATLAB/R*")
    matlab_root = matlab_path[0] + "/bin/matlab"
elif Path.home().joinpath("MATLAB/bin/matlab").is_file():
    matlab_root = str(Path.home().joinpath("MATLAB/bin/matlab"))
elif Path.home().joinpath("matlab/bin/matlab").is_file():
    matlab_root = str(Path.home().joinpath("matlab/bin/matlab"))
else:
    raise SystemExit("MATLAB not found")

if full_config["concatenate_recordings"]:
    # If concatenate_recordings is set to true, search emg data folder for existing concatenated_data
    # folder, if it exists, check subfolder names to see if they match the recording numbers
    # specified in the config file. If they don't, create a new subfolder
    # and concatenate the data into that folder. If they do, ensure that the continuous.dat file
    # exists in the continuous/ folder for the matching recordings_str folder. If it doesn't,
    # create a new subfolder and concatenate the data into that folder.
    recordNodePath = find("Record Node", full_config["working_folder"], recursive=False)
    assert (
        len(recordNodePath) == 1
    ), "Please remove all but one 'Record Node ###' folder in the Open Ephys data folder"
    concatDataPath = find("concatenated_data", recordNodePath[0])
    if full_config["emg_recordings"][0] == "all":
        Record_Node_dir_list = [
            iDir
            for iDir in os.listdir(full_config["working_folder"])
            if "Record Node" in iDir
        ]
        assert (
            len(Record_Node_dir_list) == 1
        ), "Please remove all but one 'Record Node ###' folder"
        Record_Node_dir = Record_Node_dir_list[0]
        Experiment_dir_list = [
            iDir
            for iDir in os.listdir(
                os.path.join(full_config["working_folder"], Record_Node_dir)
            )
            if iDir.startswith("experiment")
        ]
        assert (
            len(Experiment_dir_list) == 1
        ), "Please remove all but one 'experiment#' folder"
        Experiment_dir = Experiment_dir_list[0]
        recordings_dir_list = [
            iDir
            for iDir in os.listdir(
                os.path.join(
                    full_config["working_folder"], Record_Node_dir, Experiment_dir
                )
            )
            if iDir.startswith("recording")
        ]
        recordings_dir_list = [
            int(i[9:]) for i in recordings_dir_list if i.startswith("recording")
        ]
        full_config["emg_recordings"] = recordings_dir_list
    recordings_str = ",".join([str(i) for i in full_config["emg_recordings"]])

    if len(concatDataPath) > 1:
        raise SystemExit(
            "There shouldn't be more than one concatenated_data folder in the working_folder"
        )
    elif len(concatDataPath) == 1:
        exact_match_recording_folder = [
            iFolder
            for iFolder in os.listdir(concatDataPath[0])
            if recordings_str == iFolder
        ]
        if len(exact_match_recording_folder) == 1:
            # now check in the continuous/ folder for the 'Acquisition_Board-100.Rhythm Data' or
            # 'Rhythm_FPGA-100.0' folder, which should contain the concatenated data
            continuous_folder = os.path.join(
                concatDataPath[0], exact_match_recording_folder[0], "continuous"
            )
            rhythm_folder = [
                iFolder
                for iFolder in os.listdir(continuous_folder)
                if "Rhythm" in iFolder
            ]
            if len(rhythm_folder) == 1:
                continuous_dat_folder = os.path.join(
                    continuous_folder, rhythm_folder[0]
                )
                # check if continuous.dat file exists in the continuous_dat_folder folder
                if "continuous.dat" in os.listdir(continuous_dat_folder):
                    continuous_dat_is_present = True
                else:
                    continuous_dat_is_present = False
            else:
                raise FileNotFoundError(
                    f"There should be exactly one '*Rhythm*' folder in {continuous_folder},"
                    f" but found {len(rhythm_folder)}\n"
                    f"{rhythm_folder}"
                )
        else:
            continuous_dat_is_present = False

    # elif concatenating data and no continuous.dat file found in the concatenated_data folder for the
    # matching recordings_str folder
    if len(concatDataPath) < 1 or not continuous_dat_is_present:
        print(
            "Concatenated files not found, concatenating data from data in chosen recording folders"
        )
        # path_to_add = repo_folder + "/sorting/emg/"
        # subprocess.run(
        #     [
        #         f"{matlab_root}",
        #         "-nodesktop",
        #         "-nodisplay",
        #         "-nosplash",
        #         "-r",
        #         "rehash toolboxcache; restoredefaultpath;"
        #         f"addpath(genpath('{path_to_add}')); concatenate_recordings('{full_config['emg_data_folder']}', {{{full_config['emg_recordings']}}})",
        #     ],
        #     check=True,
        # )
        concatenate_emg_data(
            full_config["working_folder"], full_config["emg_recordings"]
        )
        # find the newly concatenated_data folder
        concatDataPath = find("concatenated_data", recordNodePath[0])
        assert (
            len(concatDataPath) == 1
        ), f"There should be 1 concatenated_data folder, but found {len(concatDataPath)}"
        print(
            f"Using newly concatenated data at {str(concatDataPath[0])+'/'+recordings_str}"
        )
    # elif setting is enabled and concatenated data was found with requested recordings present
    elif recordings_str in os.listdir(concatDataPath[0]):
        print(
            f"Using existing concatenated data at {str(concatDataPath[0])+'/'+recordings_str}"
        )
    concatDataPath = str(concatDataPath[0]) + "/" + recordings_str
else:
    print("Not concatenating any emg data")
    recordings_str = str(full_config["emg_recordings"][0])
    if (
        full_config["emg_recordings"][0] == "all"
        or len(full_config["emg_recordings"]) > 1
    ):
        print(
            "WARNING: concatenate_recordings is false, but more than one recording specified"
        )

# set chosen GPUs in environment variable
GPU_str = ",".join([str(i) for i in full_config["Sorting"]["GPU_to_use"]])
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = GPU_str

full_config["repo_folder"] = repo_folder

# Save config file with up-to-date information
with open(config_file, "w") as f:
    yaml.dump(full_config, f)

# Prepare common kilosort config
with open(config_file) as f:
    this_config = yaml.load(f)

# if f"{config['repo_folder']}/tmp" folder does not exist
if not os.path.isdir(f"{full_config['repo_folder']}/tmp"):
    os.mkdir(f"{full_config['repo_folder']}/tmp")

# Proceed with emg preprocessing and spike sorting
if sort:
    this_config = {
        "GPU_to_use": np.array(full_config["Sorting"]["GPU_to_use"], dtype=int),
        "num_KS_jobs": int(full_config["Sorting"]["num_KS_jobs"]),
        "working_folder": full_config["working_folder"],
        "repo_folder": full_config["repo_folder"],
        "emg_recordings": (
            np.array(full_config["emg_recordings"], dtype=int)
            if type(full_config["emg_recordings"][0]) != str
            else full_config["emg_recordings"]
        ),
        "emg_passband": np.array(full_config["emg_passband"], dtype=float),
        "emg_sampling_rate": float(full_config["emg_sampling_rate"]),
        "num_KS_components": int(full_config["Sorting"]["num_KS_components"]),
        "time_range": np.array(full_config["time_range"], dtype=float),
        "emg_analog_chan": int(full_config["emg_analog_chan"]),
    }
    path_to_add = repo_folder + "/sorting/"
    for iGroup in range(len(full_config["Group"]["emg_chan_list"])):
        if full_config["concatenate_recordings"]:
            full_config["emg_data_folder"] = concatDataPath
        else:
            # find match to recording folder using recordings_str
            recordNodePath = find(
                "Record Node", full_config["working_folder"], recursive=False
            )
            assert (
                len(recordNodePath) == 1
            ), "Please remove all but one 'Record Node ###' folder in the Open Ephys data folder"
            f = find("recording" + recordings_str, recordNodePath[0])
            full_config["emg_data_folder"] = str(f[0])
        print(f"Using data from: {full_config['emg_data_folder']}")
        full_config["sort_group"] = iGroup
        full_config["emg_chan_map_file"] = os.path.join(
            full_config["repo_folder"],
            "channel_maps",
            full_config["Group"]["emg_chan_map_file"][iGroup],
        )
        full_config["chans"] = np.array(full_config["Group"]["emg_chan_list"][iGroup])
        full_config["remove_bad_emg_chans"] = np.array(
            full_config["Group"]["remove_bad_emg_chans"][iGroup]
        )
        full_config["remove_channel_delays"] = np.array(
            full_config["Group"]["remove_channel_delays"][iGroup]
        )
        full_config["num_chans"] = (
            full_config["Group"]["emg_chan_list"][iGroup][1]
            - full_config["Group"]["emg_chan_list"][iGroup][0]
            + 1
        )
        # need this line so ETL_emg_binary can access the config file
        savemat(f"{full_config['repo_folder']}/tmp/config.mat", full_config)
        shutil.rmtree(full_config["sorted_folder"], ignore_errors=True)
        subprocess.run(
            [
                f"{matlab_root}",
                "-nodisplay",
                "-nosplash",
                "-nodesktop",
                "-r",
                (
                    "rehash toolboxcache; restoredefaultpath;"
                    f"addpath(genpath('{path_to_add}')); ETL_emg_binary"
                ),
            ],
            check=True,
        )
        full_config["emg_binary_filename"] = str(
            Path(full_config["sorted_folder"]).joinpath("data.bin")
        )
        # finally save the config file with the new emg_binary_filename (output of ETL_emg_binary)
        savemat(f"{full_config['repo_folder']}/tmp/config.mat", full_config)

        # check if user wants to do grid search of KS params
        # if full_config["Sorting"]["do_KS_param_gridsearch"] == 1:
        #     iParams = list(
        #         ParameterGrid(full_config["Sorting"]["gridsearch_params"])
        #     )  # get iterator of all possible param combinations
        # else:
        #     # just pass an empty string to run once with chosen params
        #     iParams = [""]
        # check if user wants to do grid search of KS params

        iParams = list(
            ParameterGrid(full_config["Sorting"]["gridsearch_params"])
        )  # get iterator of all possible param combinations
        if full_config["Sorting"]["do_KS_param_gridsearch"] == 0:
            # grab the first element of the ParameterGrid iterator, which is the default dictionary
            iParams = [iParams[0]]

        # create new folders if running in parallel
        if full_config["Sorting"]["num_KS_jobs"] > 1:
            worker_ids = np.arange(full_config["Sorting"]["num_KS_jobs"])
            # ensure proper configuration for parallel jobs
            assert full_config["Sorting"]["num_KS_jobs"] <= len(
                full_config["Sorting"]["GPU_to_use"]
            ), "Number of parallel jobs must be less than or equal to number of GPUs"
            assert (
                full_config["Sorting"]["do_KS_param_gridsearch"] == 1
            ), "Parallel jobs can only be used when do_KS_param_gridsearch is set to True"
            # create new folder for each parallel job to store results temporarily
            these_configs = []
            for i in worker_ids:
                # create new folder for each parallel job
                zfill_amount = len(str(full_config["Sorting"]["num_KS_jobs"]))
                new_sorted_folder = full_config["sorted_folder"] + str(i).zfill(
                    zfill_amount
                )
                if os.path.isdir(new_sorted_folder):
                    shutil.rmtree(new_sorted_folder, ignore_errors=True)
                shutil.copytree(full_config["sorted_folder"], new_sorted_folder)
                # create a new config file for each parallel job
                this_config = full_config.copy()
                this_config["sorted_folder"] = new_sorted_folder
                these_configs.append(this_config)
            # split iParams according to number of parallel jobs
            iParams_split = np.array_split(
                iParams, full_config["Sorting"]["num_KS_jobs"]
            )
            # run parallel jobs
            # with concurrent.futures.ProcessPoolExecutor() as executor:
            #     executor.map(
            #         run_KS_sorting,
            #         iParams_split,
            #         worker_ids,
            #         full_config["Sorting"]["num_KS_jobs"] * [full_config],
            #         full_config["Sorting"]["num_KS_jobs"] * [this_config],
            #     )
            # replace the above with multiprocessing
            with Pool(full_config["Sorting"]["num_KS_jobs"]) as pool:
                pool.starmap(
                    run_KS_sorting,
                    zip(
                        iParams_split,
                        worker_ids,
                        full_config["Sorting"]["num_KS_jobs"] * [full_config],
                        these_configs,
                    ),
                )
        else:
            worker_id = 0  # scalar for single job
            # run single job
            run_KS_sorting(iParams, worker_id, full_config, this_config)

# Proceed with post-processing
if post:
    this_config = {
        "repo_folder": full_config["repo_folder"],
        "working_folder": full_config["working_folder"],
        "GPU_to_use": full_config["Sorting"]["GPU_to_use"],
    }
    path_to_add = repo_folder + "/sorting/"
    for iGroup in range(len(full_config["Group"]["emg_chan_list"])):
        f = glob.glob(this_config["working_folder"] + "/Record*")

        this_config["sorted_folder"] = (
            (this_config["working_folder"] + "/sorted" + str(iGroup))
            if "-d" not in opts
            else (this_config["working_folder"] + "/" + previous_sort_folder_to_use)
        )
        this_config["emg_chan_map_file"] = os.path.join(
            full_config["repo_folder"],
            "channel_maps",
            full_config["Group"]["emg_chan_map_file"][iGroup],
        )
        this_config["remove_bad_emg_chans"] = np.array(
            full_config["Group"]["remove_bad_emg_chans"][iGroup]
        )
        this_config["remove_channel_delays"] = np.array(
            full_config["Group"]["remove_channel_delays"][iGroup]
        )
        this_config["num_chans"] = (
            full_config["Group"]["emg_chan_list"][iGroup][1]
            - full_config["Group"]["emg_chan_list"][iGroup][0]
            + 1
        )

        savemat(f"{full_config['repo_folder']}/tmp/config.mat", this_config)
        shutil.rmtree(this_config["sorted_folder"] + "/Plots", ignore_errors=True)

        print("Starting resorting of " + this_config["sorted_folder"])
        savemat(f"{full_config['repo_folder']}/tmp/config.mat", this_config)
        ## get intermediate merge folders -- (2023-09-11) not doing intermediate merges anymore
        # merge_folders = Path(f"{this_config['sorted_folder']}/custom_merges").glob(
        #     "intermediate_merge*"
        # )
        subprocess.run(
            [
                f"{matlab_root}",
                "-nodisplay",
                "-nosplash",
                "-nodesktop",
                "-r",
                (
                    "rehash toolboxcache; restoredefaultpath;"
                    f"addpath(genpath('{path_to_add}')); myomatrix_call"
                ),
            ],
            check=True,
        )

        # # extract waveforms for Phy FeatureView
        # for iDir in merge_folders:
        #     # create symlinks to processed data
        #     Path(f"{iDir}/proc.dat").symlink_to(Path("../../proc.dat"))
        #     # run Phy extract-waveforms on intermediate merges
        #     subprocess.run(["phy", "extract-waveforms", "params.py"], cwd=iDir, check=True)
        # create symlinks to processed data
        Path(
            f"{this_config['sorted_folder']}/custom_merges/final_merge/proc.dat"
        ).symlink_to(Path("../../proc.dat"))
        # run Phy extract-waveforms on final merge
        subprocess.run(
            ["phy", "extract-waveforms", "params.py"],
            cwd=f"{this_config['sorted_folder']}/custom_merges/final_merge",
            check=True,
        )

        # copy sorted0 folder tree into same folder as for -sort
        try:
            merge_path = "custom_merges/final_merge"
            shutil.copytree(
                Path(this_config["sorted_folder"]).joinpath(merge_path),
                Path(this_config["sorted_folder"])
                .parent.joinpath(previous_sort_folder_to_use)
                .joinpath(merge_path),
            )
        except FileExistsError:
            print(
                f"WARNING: Final merge already exists in {previous_sort_folder_to_use}, files not updated"
            )
        except:
            raise

# plot to show spikes overlaid on electrophysiology data, for validation purposes
if plot:
    path_to_add = repo_folder + "/sorting/"
    if "-d" in opts:
        sorted_folder_to_plot = previous_sort_folder_to_use
        args = args[1:]  # remove the -d flag related argument
    # create default values for validation plot arguments, if not provided
    if len(args) == 1:
        arg1 = int(1)  # default to plot chunk 1
        arg2 = "true"  # default to logical true to show all clusters
    elif len(args) == 2:
        arg1 = int(args[1])
        arg2 = "true"  # default to logical true to show all clusters
    elif len(args) == 3:
        import json

        arg_as_list = json.loads(args[2])
        arg1 = int(args[1])
        arg2 = np.array(arg_as_list).astype(int)
    subprocess.run(
        [
            f"{matlab_root}",
            "-nodesktop",
            "-nosplash",
            "-r",
            (
                "rehash toolboxcache; restoredefaultpath;"
                f"addpath(genpath('{path_to_add}')); spike_validation_plot({arg1},{arg2})"
            ),
        ],
        check=True,
    )

if phy:
    path_to_add = repo_folder + "/sorting/"
    if "-d" in opts:
        sorted_folder_to_plot = previous_sort_folder_to_use
        args = args[1:]  # remove the -d flag related argument
    else:
        # default to sorted0 folder, may need to update to be flexible for sorted1, 2, etc.
        sorted_folder_to_plot = "sorted0"
    os.chdir(Path(full_config["working_folder"]).joinpath(sorted_folder_to_plot))
    subprocess.run(
        [
            "phy",
            "template-gui",
            "params.py",
        ],
    )

print("Pipeline finished! You've earned a break.")
finish_time = datetime.now()
time_elapsed = finish_time - start_time
# use strfdelta to format time elapsed
print(
    (
        "Time elapsed: "
        f"{strfdelta(time_elapsed, '{hours} hours, {minutes} minutes, {seconds} seconds')}"
    )
)

# reset the terminal mode to prevent not printing user input to terminal after program exits
subprocess.run(["stty", "sane"])
