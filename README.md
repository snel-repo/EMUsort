<img width="1024px" style="max-width: 50%" alt="stylized, electrified emu before an array of white neural waveforms" src="images/emu_voltage2.png"/>

# Enhanced Motor Unit sorter (EMUsort)

### command-line tool for high-performance spike sorting of multi-channel, single-unit electromyography

- Use a central config file to control all parameters
- Capable of automatically handling Intan, OpenEphys, NWB, and Binary datasets
  - Combine recordings into single object for unified processing
  - Remove broken or noisy channels automatically
  - Perform spike sorting with a modified version of Kilosort4 for 5-10% accuracy boost (see paper)
  - Export results and easily view in Phy

## Installation

### Requirements

- Currently, using a Linux-based OS is recommended. The code has been tested on Ubuntu. Windows is supported, but may require additional configuration steps as specified below. MacOS is not supported, but might work if it is macOS version >=12.3 and has an Apple silicon or AMD GPU, however, it is untested and tailored instructions are not provided.
- GPUs with compute capability >=5.0 are supported
- Nvidia Driver:
  - Linux: >=450.80.02
  - Windows: >=452.39
- CUDA Toolkit (Automatically installed with micromamba/conda environment):
  - \>=11.3

### Cloning from GitHub

Clone the repository recursively onto your machine (for example, in the home directory)

    git clone --recurse-submodules https://github.com/snel-repo/EMUsort.git

- If you accidentally ran `git clone` without `--recurse-submodules`, just delete the entire `EMUsort` folder and rerun the above command

After cloning is complete, you will need to configure a micromamba or conda environment.

### Pulling Updates from GitHub

If your cloned repo ever becomes out of date, you should likely pull updates from the main repo. To do so, navigate into the `EMUsort` folder and run:

    git pull && git submodule update

After updating, if you encounter any issues with the configuration file afterwards, you may need to reset it to default by running:

    python emusort.py --folder /path/to/session_folder --reset-config

### Python Environment Creation

Before following the below steps, make sure to navigate into the `EMUsort` folder where you cloned the repo.

#### Micromamba (Option 1, recommended for Linux)

To install micromamba and set up a micromamba environment, follow these steps:

>**Windows:** Command causes issue with PowerShell as "<" operator is reserved. Install and use GitBash shell instead.

    "${SHELL}" <(curl -L micro.mamba.pm/install.sh)

Make sure to restart terminal (manually, or use `source` to initialize micromamba in the shell), then run:

    cd /path/to/repo_folder # go into EMUsort folder
    micromamba env create -f environment.yml

>**Windows:** The final dependencies related to `pip` may not install, returning an error.
If this happened, just activate the new micromamba environment (`micromamba activate emusort`) and run:
>`pip3 install ./sorting/spikeinterface ./sorting/Kilosort4 "git+https://github.com/cortex-lab/phy.git"`

#### Conda Environment (Option 2, recommended for Windows)

To install miniconda, follow these instructions, making sure to select the option for your OS:
- https://docs.anaconda.com/miniconda/#quick-command-line-install

>**Windows:** Open Anaconda Prompt from the Start Menu, and proceed with the below commands

Run the below commands in the conda-initialized terminal:
    
    cd /path/to/repo_folder # go into EMUsort folder
    conda env create -f environment.yml

## Usage

### Python Environment Activation

Every time you open a new terminal, you must activate the environment.
If micromamba was used, activate the environment using

    micromamba activate emusort

If a conda environment was used, activate it using

    conda activate emusort

### Session Folder Structure

EMUsort relies on a main "session folder", which contains the below 4 items.
- For Intan, NWB, or Binary datasets, all you need to do is create a new session folder to contain your desired dataset files (Item #1 below)
- For Open Ephys, the session folder itself (dated folder containing 'Record Node ###') will act as the session folder.

Items #2-4, will be generated automatically inside the provided session folder.

1. Data files (several dataset formats are supported)
   - Intan RHD/RHS files
   - NWB files
   - Binary recording files
   - Record Node ### (if using OpenEphys session folder)
2. `emu_config.yaml` file
   - will be automatically generated and should be updated to make operational changes to EMUsort using the `--config` (or `-c`) command-line option
3. `sorted_HHMMSS_ffffff_g#_<session_folder>_Th#_spkTh#` folders (tagged with datetime stamp, session folder name, group ID, and parameters used)
   - Each time a sort is performed, a new folder will be created in the session folder with the date and time of the sort. Inside this sorted folder will be the sorted data, the phy output files, and a copy of the parameters used to sort the data (`ops.npy` includes channel delays under `ops['preprocessing']['chan_delays']`). The original dataset files will not be modified.
4. `concatenated_data` folder
   - will be automatically created if the `emg_recordings` field has more than one entry, such as `[0,1,2,7]` or `[all]`, which automatically includes all recordings in the session folder

### Example Folder Tree

![Alt text](images/folder_tree_structure.png)

### EMUsort Commands

To show a helpful summary of EMUsort commands:

    python emusort.py --help

To simply generate a config file (if it doesn't exist), navigate into the `EMUsort` repo folder and run (absolute/relative paths are both acceptable):

    python emusort.py --folder /path/to/session_folder

Editing the main configuration file can be done by running the command below (will be generated if it doesn't exist):

    python emusort.py --folder /path/to/session_folder --config

To run a sort on the dataset(s) in the session folder, run:

    python emusort.py --folder /path/to/session_folder --sort

If a problem occurs with your `emu_config.py` file and you would like to reset to the default, run:

    python emusort.py --folder /path/to/session_folder --reset-config

To perform multiple operations in sequence, you can append any combination of the below commands to the command-line after `python emusort.py`

    --folder, -f
    --config, -c
    --sort, -s
    --reset-config

For example, if you want to reset to default config, configure it, and then spike sort immediately, you can run all commands at once with: `python emusort.py --reset-config -csf /path/to/session_folder`

### Inspecting and Curating with `phy`

To view and analyze the latest sort with Phy GUI, navigate into the `sorted_###` folder, and run:

    phy template-gui params.py

For more information on `phy`, see documentation at the main repo: [https://phy.readthedocs.io/en/latest/](<[url](https://phy.readthedocs.io/en/latest/)>)

## Advanced Usage

### Automatically Activate the Environment

To automatically activate the environment each time you open a new terminal, append to the end of your `~/.bashrc` file the activation command, like below:

    echo "micromamba activate emusort" >> ~/.bashrc

or

    echo "conda activate emusort" >> ~/.bashrc

depending on which environment manager you are using

### Grid Search Over Multiple Kilosort Parameters to Produce Many Sorts in Parallel

If you want to run a grid search over a range of KS parameters, edit `emu_config.py` under the `Sorting` section and set the `do_KS_param_gridsearch` field to `true`. Above it, modify `GPU_to_use` to include as many/whichever GPUs you'd like. Modify `num_KS_jobs` to specify how many jobs you'd like each GPU to run to achieve parallel processing.

Be aware of the combinatorics so you don't generate more sorts than you expected (e.g., NxM combinations for N of param1 and M of param2).

## Final Notes

If there are any discrepancies in instructions between the README and any comments/code, please let us know by submitting an issue on GitHub.

Thank you for trying out `EMUsort`! We hope you enjoy it.
