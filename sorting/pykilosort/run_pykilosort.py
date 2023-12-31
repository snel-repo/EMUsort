import os
import sys
import glob
import h5py

script_folder = os.path.dirname(os.path.realpath(__file__))
sys.path.append(script_folder)

from pathlib import Path
from pykilosort.ibl import run_spike_sorting_ibl, ibl_pykilosort_params

def kilosort(config):
    bin_file = Path(config['neuropixel'])
    ks_output_dir = Path(config['neuropixel_folder'] + '/sorted')
    scratch_dir = ks_output_dir
    ks_output_dir.mkdir(parents=True, exist_ok=True)
    params = ibl_pykilosort_params([bin_file])

    registered_file = glob.glob(config['neuropixel_folder'] + '/NeuropixelsRegistration2/' + 'subtraction_*.h5')
    with h5py.File(registered_file[0], "r") as f:
        dispmap = f["dispmap"][:]

    params['disp_map'] = dispmap.tolist()
    params['sig_datashift'] = 50.0
    params['minfr_goodchannels'] = 0
    run_spike_sorting_ibl(bin_file, delete=True, scratch_dir=scratch_dir, alf_path=None,
                          ks_output_dir=ks_output_dir, log_level='INFO', params=params, stop_after='drift_correction')

    # correct params.py to point to the shifted data
    with open(str(ks_output_dir) + '/params.py', 'w') as f:
        f.write("dat_path = 'proc.dat'\nn_channels_dat = 384\ndtype = 'int16'\noffset = 0\n" +
                "hp_filtered = True\nsample_rate = 30000\ntemplate_scaling = 20.0")
