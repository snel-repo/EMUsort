load('/tmp/config.mat')
if num_chans == 16
    load([script_dir '/geometries/bipolar_test_kilosortChanMap'])
elseif num_chans == 32
    load([script_dir '/geometries/monopolar_test_kilosortChanMap'])
end
params.chanMap = cat(2, xcoords, ycoords);
params.kiloDir = myomatrix_folder;
params.binaryFile = [myomatrix_folder '/proc.dat'];
params.userSorted = false;
params.savePlots = true;
params.waveCount = 1000;
params.consistencyThreshold = 0.7;
params.crit = 0.7;
params.skipFilter = false;
% make sure a sorting exists
if isfile([myomatrix_folder '/spike_times.npy'])
    resorter(params)
else
    disp('No spike sorting to post-process')
end

quit;