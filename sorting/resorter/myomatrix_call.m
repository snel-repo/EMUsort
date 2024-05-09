project_folder = pwd; % get folder where repo exists
load(fullfile(project_folder, '/tmp/config.mat'))
load(fullfile(sorted_folder, 'brokenChan.mat'))

% % set GPU to use
% disp(strcat("Setting GPU device to use: ", num2str(GPU_to_use)))
% gpuDevice(GPU_to_use);

% load channel map with broken channels removed if chosen by user
if length(brokenChan) > 0 && remove_bad_emg_chans(1) ~= false
    load(fullfile(sorted_folder, 'chanMapAdjusted.mat'))
else
    load(emg_chan_map_file)
end

% resorting parameters
params.chanMap = cat(2, xcoords, ycoords);
params.kiloDir = [sorted_folder '/custom_merges'];
params.binaryFile = [sorted_folder '/data.bin'];
params.doPlots = true; % whether to generate plots
params.savePlots = true; % whether to save plots
params.skipFilter = false;
params.SNRThresh = 2.0;
params.corrThresh = 0.9; % minimum correlation to be considered as originating from one cluster
params.consistencyThresh = 0.6; % minimum consistency to be considered as originating from one cluster
params.spikeCountLim = 100; % minimum spike count to be included in output
params.refractoryLim = 0.5; % spikes below this refractory time limit will be considered duplicates

% make sure a sorting exists
if isfile([sorted_folder '/spike_times.npy'])
    resorter(params)
else
    disp('No spike sorting to post-process')
end

quit;
