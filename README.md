<img width="1024px" style="max-width: 50%" alt="stylized, electrified emu before an array of white waveforms" src="images/emu_voltage2.png"/>

# Enhanced Motor Unit sorter (EMUsort)

### A command line tool for high performance spike sorting of multichannel, single unit electromyography

- Perform spike sorting with a modified version of Kilosort4 specifically tailored to MUAP data for improved performance (see paper for performance comparison results)
- Use a central configuration file to control all parameters and perform parameter sweeps
- Capable of automatically handling Intan, OpenEphys, NWB, Blackrock, and Binary datasets
- Combine recordings into single object for unified processing
- Remove broken or noisy channels automatically
- Export results and easily view in Phy

## Installation

### Requirements

- Currently, using a Linux-based OS is recommended. The code has been tested on Ubuntu. Windows is supported, but may require additional configuration steps as specified below. MacOS is not supported, but might work if it is macOS version >=12.3 and has an Apple silicon or AMD GPU, however, it is untested and tailored instructions are not provided.
- GPUs with compute capability >=5.0 are supported
- Nvidia Driver:
  - Linux: >=450.80.02
  - Windows: >=452.39
- CUDA Toolkit (Automatically installed with the environment):
  - \>=11.3

### Cloning from GitHub

Clone the repository recursively onto your machine (for example, in the home directory)

    git clone --recurse-submodules https://github.com/snel-repo/EMUsort.git

> If you accidentally ran `git clone` without `--recurse-submodules`, just delete the entire `EMUsort` folder and rerun the above command

After cloning is complete, you will need to configure a uv, micromamba, or conda environment.

### Pulling Updates from GitHub

To update your `EMUsort` clone to the latest version, you can pull updates from the main repository. To do so, navigate into the folder where `EMUsort` was cloned and run:

    git pull && git submodule update

If you are updating and already previously installed EMUsort, you may encounter issues with the configuration file (if it's structure changed). If this happens, you can reset it to the default configuration file by running:

    emusort --reset-config --folder /path/to/session_folder

### Python Environment Creation

Before following the below steps, make sure to navigate into the folder where `EMUsort` was cloned.

#### Option 1: [`uv`](https://docs.astral.sh/uv/)
**Recommended for Windows and Linux (see Option 2 if using Linux over RDP)**

Follow the steps and execute the commands below to install and manage EMUsort with `uv`, a high performance Python package and project manager:

> **Windows only:** Install [GitBash](https://gitforwindows.org/) first with default settings and use its shell to use EMUsort.

    curl -LsSf https://astral.sh/uv/install.sh | sh

Then either restart the terminal or execute the command suggested in the terminal to enable using `uv` in the terminal. Next, create the environment and install all dependendencies including Phy, using `uv`:

    cd /path/to/repo_folder # go into the EMUsort clone location  
>**Windows only:** Windows seems most stable using Python version 3.9, so be sure to use the `--python 3.9` option with the below command.
>For example: `uv sync --extra full --python 3.9`.
>Other Python versions can be tried afterwards, if necessary.

Use `uv` to execute the installation with the "full" option, which will install Kilosort4 (with modifications), SpikeInterface, PyTorch, and Phy GUI. See `pyproject.toml` for more "--extra" options.

    uv sync --extra full

If the install finished successfully, proceed to the [Usage](https://github.com/snel-repo/EMUsort?tab=readme-ov-file#usage) section next.

#### Option 2: [`micromamba`](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html)
**Recommended for Linux (remote, e.g., for use over Remote Desktop with X11 on remote system)**

To install `micromamba` and set up a `micromamba` environment, follow the steps and execute the commands below:

> **Windows only:** Install [GitBash](https://gitforwindows.org/) first with default settings and use its shell to use EMUsort.

    "${SHELL}" <(curl -L micro.mamba.pm/install.sh)

If this errors out, you can simply download the script from `micro.mamba.pm/install.sh` and run a file with those contents manually with `bash ./install.sh`.
Afterwards, make sure to either restart the terminal or [initialize](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html) `micromamba` directly, then run the below commands:

    cd /path/to/repo_folder # go into the EMUsort clone location
    micromamba env create -f environment.yml

> **Windows only:** During micromamba environment creation, the conda packages usually work, but you may get an error at the end related to the `pip` packages not install installing.
> If this happened, it's likely micromamba worked, but the `pip` packages need manual installation. This is a Windows problem. So, go ahead and activate the micromamba environment you just created (`micromamba activate emusort`), and run the following, one by one:
> `pip install -e ./src/emusort/spikeinterface`
> `pip install -e ./src/emusort/Kilosort4`
> `pip install "git+https://github.com/cortex-lab/phy.git@7a2494b"`
> `pip install -e .`
> If you encounter errors installing spikeinterface or Kilosort4, try navigating into each submodule folder and running `pip install -e .` to install the packages manually. Then `pip install -e .` in the main folder again to install the main EMUsort package.

If the install finished successfully, proceed to the [Usage](https://github.com/snel-repo/EMUsort?tab=readme-ov-file#usage) section next.

#### Option 3: [`anaconda/miniconda`](https://www.anaconda.com/docs/getting-started/miniconda/main)
**Fallback Method, No Longer Recommended**

To install `miniconda`, follow the link below, making sure to select the correct option for your OS:

- https://www.anaconda.com/docs/getting-started/miniconda/install#quickstart-install-instructions

> **Windows only:** Open Anaconda Prompt from the Start Menu, and proceed with the below commands

Make sure restart the terminal or [initialize](https://www.anaconda.com/docs/getting-started/miniconda/install#manual-shell-initialization) `conda` in the terminal, then run the below commands:

    cd /path/to/repo_folder # go into the EMUsort clone location
    conda env create -f environment.yml

## Usage

### Python Environment Activation

Every time you open a new terminal, the environment must be activated, whether manually or automatically (see [Advanced Usage](https://github.com/snel-repo/EMUsort?tab=readme-ov-file#advanced-usage) for automatic activation).

#### Option 1: `uv`

*Linux only:*

    source /path/to/repo_folder/.venv/bin/activate

*Windows only*:

    source /path/to/repo_folder/.venv/Scripts/activate

#### Option 2: `micromamba`

    micromamba activate emusort

#### Option 3: `anaconda/miniconda`

    conda activate emusort

### Session Folder Structure

EMUsort relies on a main "session folder", which contains the below 4 items.

- For Intan, NWB, Blackrock, or Binary datasets, all you need to do is create a new session folder to contain your desired dataset files (Item #1 below).
- For Open Ephys, the session folder itself (dated folder containing 'Record Node ###') will act as the session folder. The original dataset files will not be modified.

Items #2-4, will be generated automatically inside the provided session folder.

1. Data files (several dataset formats are supported)
   - Intan RHD/RHS files
   - NWB files
   - Blackrock files
   - Binary recording files
   - Record Node ### (if using OpenEphys session folder)
2. `emu_config.yaml` file
   - will be automatically generated and should be updated to make operational changes to EMUsort using the `--config` (or `-c`) command line option. Within the config file, please note that you will have to change the `dataset_type` attribute to match your desired dataset type. Once you generate the default config template, please review it and utilize the comments as documentation to guide your actions
3. `sorted_yyyyMMdd_HHmmssffffff_g#_<session_folder>_Th#_spkTh#` folders (tagged with datetime stamp, group ID, session folder name, and parameters used)
   - Each time a sort is performed, a new folder will be created in the session folder with the date and time of the sort. Inside this sorted folder will be the sorted data, the phy output files, and a copy of the parameters used to sort the data (`ops.npy` includes channel delays under `ops['preprocessing']['chan_delays']`). The corresponding channel indexes for each sort are saved as `emg_chans_used.npy`. In each new sort folder, the `emu_config.yaml` is also dumped for future reference, which also includes channel indexes used in each sort as `emg_chans_used`.
4. `concatenated_data` folder
   - will be automatically created if the `emg_recordings` field has more than one entry, such as `[0,1,2,7]` or `[all]`, which automatically includes all recordings in the session folder

### Example Folder Tree

#### Intan, NWB, Blackrock, and Binary datasets:

![Alt text](images/folder_tree_structure.png)

#### Open Ephys datasets:

![Alt text](images/OE_folder_tree_structure.png)

### EMUsort Commands

To show a helpful summary of EMUsort commands:

    emusort --help

To simply generate a config file (if it doesn't exist), run the below command:  

>**Note:** Absolute and relative paths are both acceptable.

    emusort --folder /path/to/session_folder

Editing the main configuration file, `emu_config.py`, can be done by running the command below (will be generated from `configs/config_template_emu.yaml` if it doesn't exist):

    emusort --config --folder /path/to/session_folder

If a problem occurs with your `emu_config.py` file and you would like to reset it to the default at `configs/config_template_emu.yaml`, you can run:

    emusort --reset-config --folder /path/to/session_folder

To run a sort directly with the current `emu_config.py` on the dataset(s) in the session folder, run:

    emusort --sort --folder /path/to/session_folder

For Kilosort4 emulation runs, you can include the `--ks4` flag. See [Running EMUsort As If Default Kilosort4](https://github.com/snel-repo/EMUsort?tab=readme-ov-file#running-emusort-as-if-default-kilosort4-v4011) for more details.


If you want to specify multiple settings at the same time, you can append any combination of the below commands to the command line after `emusort`.

>**Note:** For all commands, there is a short-form equivalent. The flags can be used in any order, but the path must always follow directly after the `--folder` flag.

    --help, -h
    --folder /path/to/session_folder, -f ./session_folder
    --config, -c
    --reset-config, --r
    --sort, -s
    --ks4, -k

As an example of using multiple commands, if you want to reset to the default configuration file, edit the new `emu_config.yaml`, and also spike sort immediately after saving, you can run the below:

    emusort --reset-config --config --sort --folder /path/to/session_folder

### Inspecting and Curating with `phy`

To view and analyze the latest sort with Phy GUI, you can either copy and paste the suggested `phy` command in the terminal output, or navigate into the latest `sorted_###` folder, and execute:

    phy template-gui params.py

For more information on `phy`, see the documentation at the main GitHub repository: [https://phy.readthedocs.io/en/latest/]([url](https://phy.readthedocs.io/en/latest/))

## Advanced Usage

### Automatically Activate the Environment

To automatically activate the environment each time you open a new terminal, append to the end of your `~/.bashrc` file the activation command, depending on which environment manager you are using, execute:

>**Windows only**: If using GitBash (recommended), you may need to replace `~/.bashrc` with `~/.bash_profile` in the below commands. For `uv`, you must also swap to `"source /path/to/repo_folder/.venv/Scripts/activate"`.

**uv:** 
    
    echo "source /path/to/repo_folder/.venv/bin/activate" >> ~/.bashrc # USING YOUR VALID PATH

**micromamba:**
    
    echo "micromamba activate emusort" >> ~/.bashrc # USING YOUR VALID PATH

**conda:**
    
    echo "conda activate emusort" >> ~/.bashrc # USING YOUR VALID PATH

### Parameter Sweep Over Multiple Kilosort Parameters to Produce Many Sorts in Parallel

If you want to run multiple sort jobs in parallel across a range of KS parameters, edit `emu_config.py` under the `Sorting` section and set the `do_KS_param_sweep` field to `true`. Above it, modify `GPU_to_use` to include all the GPUs that should be used. Modify `num_KS_jobs` to specify how many total jobs to distribute across all chosen GPUs.

Be aware of the combinatorics so you don't generate more sorts than you expected (e.g., NxM combinations for N of param1 and M of param2).

### Running EMUsort As If Default Kilosort4 (v4.0.11)

In order to run EMUsort exactly like a default Kilosort4 (v4.0.11) installation for comparison of performance, you can use the short-form command `emusort -kcsf .` to run it in the current folder, or use the below, longer-form command:

    emusort --ks4 --config --sort --folder /path/to/session_folder

This will generate a default Kilosort4 config file and run the sort with it. It does not interfere with the main `emu_config.yaml` file because it is a separate config file named `ks4_config.yaml`. 

To only adjust the `ks4_config.py` in the session folder without performing spike sorting, you can run:
    
    emusort --ks4 --config --folder /path/to/session_folder

To reset the `ks4_config.py` file to default from `configs/config_template_ks4.yaml` and edit it, run:

    emusort --reset-config --ks4 --config --folder /path/to/session_folder

To run Kilosort4 emulation, reset `ks4_config.yaml` to default settings, edit the new `ks4_config.yaml`, and perform spike sorting in the current folder, all in one compact command, you can run the below command:

    emusort --r -kcsf .

This emulation capability is useful for comparing the performance of EMUsort vs. Kilosort4.

## Final Notes

If there are any discrepancies in the instructions or any problems with the comments/code, please submit an issue on GitHub so we can try to address the issue ASAP.

Thank you for trying out EMUsort! If you find it helpful, enjoy it, or love emus, give us a ⭐️ on GitHub!
