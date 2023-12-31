% ksGUI_updatePars.m
% 
% script to update GUI pars with recommend settings for stereo Uprobes (32 chan, 50/100 um geometry)
% 
% see in-line comments for further info
% 
% 2020-xx-xx  TBC  Wrote it.  (github.com/czuba)
% 2022-xx-xx  TBC  rolling revisions...
% 

fprintf(['\n',repmat('=-',1,20),'\n']);

%% Retrieve gui settings
ks = get(figure(1029321), 'UserData'); % use standard kilosort [magic] figure number to select proper handle
ops = ks.ops
ops0 = ops; % backup initial ops settings

fprintf([repmat('--',1,20),'\n']);

%% Apply standard updates (subfunction)
ops = standardOpsTweaks(ops);


%% Refine ops for particular recording session(s)
% % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
% Common session-sepcific tweaks
%   ops.Th          cluster sort threshold [learn, extract], def==[8 2]
%                   - ** output files trend very/prohibitively large for learn threshold <=6 **
%                   - learn value:   inc. to 10 for especially high SNR, or dec. to 6 for low SNR
%                   - extract value: inc. to 4 for less manual trimming, but possible clipping; <2 not recommended
%
%   ops.momentum    maleability/history parameter of template temporal dynamics, def==[80 800]
%                   - new clusters start at first val & progress to latter val across learning batches
%                   - momentum fixed at latter value throughout extraction phase
%                   - if significant probe drift, try [80 600] or [40 400]
%                   - if set too low, clusters will smear across units (w/in channel) rather than follow a unit across channels (...untractably so)
%
%   ops.targBatch   target batch for drift tracking, def==0.5
%                   - only consider changes if default happens to fall between stimulus files, or during an epoch of significant drift/irregularity
%                   - >0 & <1, fractional position w/in file; integer>=1, specific batch#;  avoid extremes (<25/50 batches from start or finish)
%
%   ops.middleout   binary flag to process batches during extraction as [ops.targBatch:-1:1] then [ops.targBatch+1:1:end], def==0
%                   - try if significant probe drift and/or start of file is less representative of session (i.e. no stimulus, or modest settling)
% 
%   ops.trange      *[not recommended]* constrain sorting to a subset of file: [tstart, tend] in sec,  def==[0, inf]
% % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
%
% EXAMPLE session refinements:
%     % Session 20210826 s01, plx d
%     % ...more drifty than usual/desired
%     ops.targBatch = 0.4;
%     ops.middleOut   = 1;
%     ops.momentum    = [80 400];
%     ops.Th          = [6 2];
%
% % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 


%% Apply to updates to GUI params object
fprintf('New ops settings:\n')
disp(ops)

ks.ops = ops;

% Update GUI parameter values
ks.H.settings.setFsEdt.String = num2str(ks.ops.fs);
ks.H.settings.setTrangeEdt.String = num2str(ks.ops.trange);
% !! CAUTION: jacked GUI parameter name correspondence for >=ks2.5
if any(contains(ks.H.settings.setMinfrTxt.String, 'blocks', 'ignoreCase',1))
    ks.H.settings.setMinfrEdt.String = num2str(ks.ops.nblocks); 
else
    ks.H.settings.setMinfrEdt.String = num2str(ks.ops.minfr_goodchannels);
end
ks.H.settings.setThEdt.String = num2str(ks.ops.Th);
ks.H.settings.setLambdaEdt.String = num2str(ks.ops.lam);
ks.H.settings.setCcsplitEdt.String = num2str(ks.ops.AUCsplit);

clear ops;


%% Extra Czuba components
try
    % Establish [figDir] variable in base workspace
    % - when present, saveFigTriplet.m will automatically generate figure hierarchy here
    figDir = fullfile(ks.ops.saveDir,'figs');

    % Copy _rawInfo.mat file to saveDir (generated by plx2raw.m; https://github.com/czuba/kilosort_utils)
    % - "_rawInfo.mat" is auto-generated when converting .plx/.pl2 data to raw .dat
    % - includes info structs, **as well as all sync event data**, from original source data file(s)
    % - spk repo will look for this file for interpreting sorted outputs
    [fbp,fbn] = fileparts(ks.ops.fbinary); % raw data file
    fbn = [fbn,'_rawInfo.mat']; % append rawInfo extension
    if exist(fullfile(fbp,fbn), 'file')
        copyfile(fullfile(fbp,fbn), fullfile(ks.ops.saveDir, fbn));
    end
catch
    fprintf(2, '\t\t- Unable to find/copy "_rawInfo.mat" file into kilosort output directory\n\n')
end
clear fbp fbn


%% move focus to command window
commandwindow;
% ks.updateFileSettings
fprintf(['\nDone.\tNew settings have been applied to kilosort GUI object [ks].\n',repmat('=-',1,20),'\n']);

% make entry in gui log
try
    ks.updateFileSettings;
    ks.log('Advanced Kilosort [& GUI] params updated.');
end

return
% % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
% % End ksGUI_updatePars.m script
% % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 


% % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
%% Sub Functions
% % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 

%% standardOpsTweaks(ops)
function ops = standardOpsTweaks(ops)
    % subfunction to apply standard ops settings for 32 ch stereoprobe recordings
    %   (Plexon Uprobes/Sprobes, stereotrode spacing 50/100 um [within/between])
    
    %% Custom fields or flags
    % Parallel memmap raw data for whitening/loading
    % - requires use of get_whitening_matrix_faster.m w/in preprocessDataSub.m
    ops.useMemMapping   = 1;
    
    ops.fig = 1; % 1==standard plots, 2=extra debug plots (more verbose, but marginally slower)
    
    % drift correction params (see datashift2.m)
    %   U-Probe recommendation:  ops.nblocks = 1;  ops.integerShifts = 1;
    % 
    % [.nblocks] type of data shifting (0 = none, 1 = rigid, 2 = nonrigid)
    ops.nblocks = 0; % non-rigid only really relevant for mmmany channels or probe length is long relative to brain (i.e. rodents)
    
    % flag to round [data]shifts to nearest electrode spacing integer
    % - ALWAYS use integerShifts
    ops.integerShifts = 1;
    
    % preselect target batch for drift alignment
    % - if  <1, will be batch nearest targBatch% of total batches
    % - if >=1, will be direct index to batch#
    % - default = 0.5;
    ops.targBatch = 0.5;
    
    % Randomize batch order during learning
    % - provides more stable/effective set of learned templates across entire file
    ops.learnRand = 1;

    % [middleout] flag for batch sequence during spike extraction
    % - if 0, extract spikes linearly in time; 1:nbatches
    % - if 1, extract spikes [ops.targBatch:-1:1] then [ops.targBatch+1:1:end]
    % - in either case, final learning phase will always pre-condition templates accordingly 
    % default == 0
    ops.middleout = 0;

    % clip template updating to a minimum number of contributing spikes
    % - helps prevent inversions (due to subtle/irregular noise being injected into dWU0 output of mexMPnu8.cu)
    % 20 spike cutoff works well for 10 sec batch
    ops.clipMin = 20;
    ops.clipMinFit = .8;  % can survive clipping if median accounts for at least this much variance (ratio of vexp./amp)
    
    % Apply detailed ccg analysis function to remove double-counted spike clusters
    % - Orig from Bondy fork, but integrated into standard around kilosort 2(.5)
    % - this is useful feature, but actually makes manual curation somewhat more challenging,
    %   because strong ccg peak is informative for merge decisions
    % - best left disabled for probes (even hopes that it would allow threshold cutoff to be less errorprone didn't work out)
    ops.rmDuplicates    = 0;
    
    % Post-hoc split clusters by:  1==template projections, 2==amplitudes, 0==don't split
    % - amplitude splits seem reasonably trustworthy (...template splits suceptible to oddities of templates (e.g. inversions))
    % ops.splitClustersBy = 2;    % (relatively safe & effective, but can mask problems w/sort parameters & fitting)
    ops.splitClustersBy = 0;    % 0 recommended for full assessment of what sorting is doing
    
    % standard cutoff can be overly aggressive
    % - best left disabled for probes
    ops.applyCutoff = 0;
    
    % Git repo status & diff
    ops.useGit = 1;
    % add kilosort_utils repo to git version tracking
    % - moved into ks25 ./configFiles dir
    % - retained here for example on how to add other repos to git tracking functionality
    % % ops.git.kilosort_utils.mainFxn = 'ksGUI_updatePars.m';
    

    %% Apply changes to standard ops
    ops.fshigh = 300; % map system has hardware high pass filters at 300
    
    % make waveform length independent of sampling rate
    % ops.nt0                 = ceil( 0.002 * ops.fs); % width of waveform templates (makes consistent N-ms either side of spike, regardless of sampling rate)
    % ops.nt0                 = ops.nt0 + mod(ops.nt0-1, 2); % ensure oddity (...forum something about aiding spike trough alignment)
    
    % when Kilosort does CAR, is on batch time blocks, which mitigates risk of steps injected btwn demeaned segments
    % -- NOTE: flag is "CAR", but uses common median referencing [CMR]
    ops.CAR                 = 1; % if >1, CAR updated for mean subtraction with outlier exclusion in prepreocessDataSub.m (slow)
    ops.useStableMode       = 1;
    ops.reorder             = 0; % this should always be disabled (==0); reordering time to fix probe drift was no good    
    
    % tries to address scaling discrepancy btwn data and template/whitened by increasing scaleproc
    % - primarily only relevant in GUI, but if waay out of scale could cause clipping depending on raw/source data format
    % - see get_whitening_matrix.m (def=200)
    ops.scaleproc = 200;    % ...no longer a crucial tweak, after standardizing raw/filtered data scaling in ksGUI.m
    
    ops.throw_out_channels = 0; % NO! confounds source identity; never throw out chans during sort
    ops.minfr_goodchannels = 0; % minimum firing rate on a "good" channel (0 to skip); always disable, see above   (def=0.1)
    
    % [minFR] prevents errant 'units' with just a few detected spikes from proliferating
    % - implementation is a little dicey with longer batch durations (5-10 sec) and/or shorter files (<1hr)
    ops.minFR = 0.02;
    
    % loosen minFR when randomizing batch order during learning
    % - clip truly useless templates, but don't drop less active ones (esp with randomized batch order during learning)
    ops.minFR = ops.minFR / max([ops.learnRand*2,1]);
    
    % threshold(s) used when establishing baseline templates from raw data
    % - standard codebase tends to [frustratingly] overwrite this param, but working to straighten out those instances
    ops.spkTh = -6;     % [def= -6]
    ops.ThPre = 8;      % [def= 8]
    
    % splitting a cluster at the end requires at least this much isolation for each sub-cluster (max = 1)
    % - only relevant if post-hoc merges & splits are used (which is not recommended, see flags above)
    ops.AUCsplit = 0.9; %0.95; % ks2 default=0.9;  ks3 default=0.8;
    
    % how important is the amplitude penalty. Original repo description: "0 means not used, 10 is average, 50 is a lot"
    ops.lam = 10;  % ks3 default is 20; previously 10...   (TBC: this has always been totally cryptic, stick with ==10)
    
    % threshold(s) on cluster template projections (def=[8 2]; original kilosort [10 4])
    % - 1-by-2 param [learn, extract]
    %   - 1st value is treshold used during template learning phases    (learnTemplates.m)
    %   - 2nd is threshold used during spike extraction phases          (trackAndSort.m)
    % - learn thresh:   8 is good; 10 for especially high SNR, 6 for low SNR
    % - extract thresh: 2 is good; 4 for less manual trimming, but possible clipping; <2 not recommended
    % ** output files trend very/prohibitively large for learn threshold <=6 **
    ops.Th = [8 2]; %[10 4];  (TBC: [8 4] better for awake nhp, but still clipping)
        

    %% Stereo-probe specific adjustments (standard geom: 50um within, 100um between stereopairs)
    % spatial constant in um for computing residual variance of spike     (def=30)
    ops.sigmaMask = 70;  % 50-70 better for 50/100um intra/inter-trode spacing; else no spread across channels
    ops.whiteningRange = 32; % use all chanels available
    
    % Spike detection: .loc_range & .long_range are used isolate threshold peaks in:
    %       [nSamples in time, nChannels];
    % - BUT relevant uprobe 'channel' units are very different from nanopixel spacing
    %       nChannels==3 will include lateral & longitudinally adjacent channels of stereo probe
    %       nChannels==5 will include adjacent stereopairs (**but b/c spacing asymmetry of channel indices, this can include channel up to 300 microns away...:-/ )
    ops.loc_range   = [5, 2];   % def=[5, 4]
    ops.long_range  = [30, 4];  % def=[30, 6]
    
    
    %% "datashift" params
    ops.sig = 20; % [20] "spatial smoothness constant for registration"
    % - drift correction not recommended for anything but qualitative assessment (which it IS very useful),
    %   but this param only influences the applied [smearing of] datashifts)
    % - can't be 0; used by standalone_detector.m & 0 will wipe out multi-scale gaussian spread of generic templates across channels
    % So looks like this param (or the often hardcoded .sig param) is used when applying datashift drift corrections in increments smaller than [y] sampling of recording sites
    % - this effectively blurrs shifted data traces into/across adjacent channels
    % - maybe doing so flies with high res sampling of neuropixels, but abruptly jacks data quality/signal on more coarsely sampled devices (e.g. uprobes)
    
    
    %% Update temporal/batch parameters
    % [.nTEMP] number of initial templates to extract from threshold crossings
    % - These form the basis for any new templates added during learning & the initial PCA dimensions
    % - If undefined, 6 is the usual number of templates, but more seems generally non-detrimental & likely helpful
    ops.nTEMP = 12;
    
    % number of samples to average over (annealed from first to second value)     (def=[20,400])
    % - approximate weight(s) of spike history filter during template learning & extraction
    % - during learning, new templates start at first value (def=80, very maleable), and progress to second value (def=800, very stable)
    % - during extraction, parameter is fixed at second value (affects degree of temporal dynamics)
    % - this param interacts with batch duration (ideally it wouldn't), for batches ~6-10 sec long, [80 800] is pretty good
    ops.momentum = [80 800];
    
    ops.nfilt_factor        = 6; % (def=4) max number of clusters per ['good'] channel (even temporary ones)
    
    % TBC version define batches in seconds of data, not abstract bit chunks
    batchSec                = 8;  % define batch number in seconds of data     (TBC: 8:10 seems good for 1-2 hr files and/or 32 channels)
    
    % samples of symmetrical buffer for batch processing whitening and spike detection
    % - must be divisible by 64; originally *just* ==64 (i.e. the minimum, barely one spike template width)
    % - longer buffer helps stabilize batch computations over fewer channels (10s, not 100s)
    bufferSec       = 2;    % 
    ops.ntbuff      =  ceil(bufferSec*ops.fs/64)*64;%  ceil(batchSec/4*ops.fs/64)*64;  % (def=64)
    
    % buffer size in samples
    ops.NT                  = ceil(batchSec*ops.fs/32)*32; % convert to 32 count increments of samples
    
    % sample from batches more sparsely (in certain circumstances/analyses)
    batchSkips              = ceil(60/batchSec); % do high-level assessments at least once every minute of data
    ops.nskip               = 1;    %batchSkips;  % 1; % how many batches to skip for determining spike PCs
    ops.nSkipCov            = batchSkips;    %batchSkips;  % 1; % compute whitening matrix from every N-th batch

end %end standardOpsTweaks

