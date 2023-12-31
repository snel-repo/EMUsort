import os
import sys
script_folder = os.path.dirname(os.path.realpath(__file__))
sys.path.append(script_folder)
import glob
from pathlib import Path
import shutil
from pykilosort import run, add_default_handler, myomatrix_bipolar_probe, myomatrix_unipolar_probe

def myo_sort(config):
    directory = config['myomatrix']
    chans = range(0, config['num_chans'])
    bin_file = directory + '/sorted' + str(config['myomatrix_num']) + '/data.bin'
    params = {'perform_drift_registration': False, 'n_channels': len(chans),
              'minfr_goodchannels': 0.1}
    data_path = Path(bin_file)
    dir_path = Path(config['myomatrix_folder'])  # by default uses the same folder as the dataset
    output_dir = dir_path
    add_default_handler(level='INFO')  # print output as the algorithm runs
    if len(chans) == 16:
        probe = myomatrix_bipolar_probe()
    elif len(chans) == 32:
        probe = myomatrix_unipolar_probe()
    else:
        error('No probe configuration available')
    run(data_path, dir_path=dir_path, output_dir=output_dir,
        probe=probe, low_memory=True, stop_after="preprocess", **params)
    post_file = glob.glob(str(dir_path) + '/.kilosort/*/proc.dat')
    try:
        shutil.move(post_file[0], str(dir_path) + '/proc.dat')
    except OSError:
        pass
    shutil.rmtree(dir_path.joinpath(".kilosort"), ignore_errors=True)

    # correct params.py to point to the shifted data
    with open(str(output_dir) + '/params.py', 'w') as f:
        f.write("dat_path = 'proc.dat'\nn_channels_dat = " + str(len(chans)) +
                "\ndtype = 'int16'\noffset = 0\n" +
                "hp_filtered = True\nsample_rate = 30000\ntemplate_scaling = 20.0")

    #os.remove(bin_file)