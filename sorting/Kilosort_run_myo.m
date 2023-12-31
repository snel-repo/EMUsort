script_dir = pwd; % get directory where repo exists
load(fullfile(script_dir, '/tmp/config.mat'))

try
    restoredefaultpath
end
dbstop if error

chanMapFile = myo_chan_map_file
disp(['Using this channel map: ' chanMapFile])

addpath(genpath([script_dir '/sorting/Kilosort-2.0']))
addpath(genpath([script_dir '/sorting/npy-matlab']))

run([script_dir '/sorting/Kilosort_config_2.m']);
ops.fbinary = fullfile(myo_sorted_dir, 'data.bin');
ops.fproc = fullfile(myo_sorted_dir, 'proc.dat');
ops.brokenChan = fullfile(myo_sorted_dir, 'brokenChan.mat');
ops.chanMap = fullfile(chanMapFile);
ops.NchanTOT = double(num_chans);

ops.nt0 = 155;
ops.NT = 4 * 64 * 1024 + ops.ntbuff; % 4*64*1024 good
ops.nskip = 10; % how many batches to skip for determining spike PCs
ops.nSkipCov = 10; % compute whitening matrix from every N-th batch
ops.reorder = 1;
ops.sigmaMask = 1e10; % we don't want a distance-dependant decay
ops.Th = [9 6]; % [9 3] good
ops.nfilt_factor = 4; %floor(1024 / ops.NchanTOT);
ops.filter = false;

if trange(2) == 0
    ops.trange = [0 Inf];
else
    ops.trange = trange;
end

ops

% preprocess data to create temp_wh.dat
rez = preprocessDataSub(ops);

% time-reordering as a function of drift
rez = clusterSingleBatches(rez);

% main tracking and template matching algorithm
rez = learnAndSolve8b(rez);

% OPTIONAL: remove double-counted spikes - solves issue in which individual spikes are assigned to multiple templates.
% See issue 29: https://github.com/MouseLand/Kilosort2/issues/29
%rez = remove_ks2_duplicate_spikes(rez, 'overlap_s', 8e-4, 'channel_separation_um', 50000);

% final merges
rez = find_merges(rez, 1);

% final splits by SVD
rez = splitAllClusters(rez, 1);

% final splits by amplitudes
rez = splitAllClusters(rez, 0);

% decide on cutoff
rez = set_cutoff(rez);

fprintf('found %d good units \n', sum(rez.good > 0))

% write to Phy
fprintf('Saving results to Phy  \n')
rezToPhy(rez, myo_sorted_dir);

delete(ops.fproc);

quit;
