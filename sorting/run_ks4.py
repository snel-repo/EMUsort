# this file will run kilosort according to my settings
# import numpy as np
from pathlib import Path
from kilosort import run_kilosort

if __name__ == "__main__":
    run_kilosort(
        settings=dict(
            n_chan_bin=8,
            nearest_chans=8,
            batch_size=600000,
            nblocks=0,
            Th_universal=9,
            Th_learned=8,
            Th_single_ch=6,
            probe_path=Path(
                "/snel/home/smoconn/git/EMUsort/geometries/linear_08ch_sequential_kilosortChanMap_2um.mat"
            ),
        ),
        filename=Path(
            "/snel/share/data/rodent-ephys/open-ephys/treadmill/sean-pipeline/godzilla/simulated20221117/2022-11-16_16-19-28_myo/Record Node 101/experiment1/concatenated_data/1,2,4,5,6,7/continuous/Acquisition_Board-100.Rhythm Data/continuous_20240301-180102_godzilla_20221117_10MU_SNR-1-from_data_jitter-16std_method-KS_templates_12-files.dat"
        ),
    )
