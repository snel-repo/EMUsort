function [channelDelays] = get_channel_delays(rez)
% based on a subset of the data, compute the channel delays to maximize cross correlations
% this requires temporal filtering first (gpufilter)

ops = rez.ops;
Nbatch = ops.Nbatch;
twind = ops.twind;
NchanTOT = ops.NchanTOT;
NT = ops.NT;
NTbuff = ops.NTbuff;
Nchan = rez.ops.Nchan;

fprintf('Getting channel delays... \n');
fid = fopen(ops.fbinary, 'r');
maxlag = ops.fs/500; % 2 ms max time shift

% we'll estimate the cross correlation across channels from data batches
ibatch = 1;
chan_CC = zeros(2*maxlag+1, NchanTOT^2, 'single', 'gpuArray');
while ibatch<=Nbatch
    offset = max(0, twind + 2*NchanTOT*((NT - ops.ntbuff) * (ibatch-1) - 2*ops.ntbuff));
    fseek(fid, offset, 'bof');
    buff = fread(fid, [NchanTOT NTbuff], '*int16');

    if isempty(buff)
        break;
    end
    nsampcurr = size(buff,2);
    if nsampcurr<NTbuff
        buff(:, nsampcurr+1:NTbuff) = repmat(buff(:,nsampcurr), 1, NTbuff-nsampcurr);
    end
    buff = gpuArray(buff);
    chan_CC_maybe_nan = xcorr(abs(buff'), maxlag, 'coeff');
    % change nans to zeros
    chan_CC_maybe_nan(isnan(chan_CC_maybe_nan)) = 0;
    chan_CC_this_batch = chan_CC_maybe_nan;
    chan_CC = chan_CC + chan_CC_this_batch;

    ibatch = ibatch + ops.nSkipCov; % skip this many batches
end
% normalize result by number of batches
chan_CC = chan_CC / ceil((Nbatch-1) / ops.nSkipCov); % chan_CC might be all NaN's because 

fclose(fid);

% find the channel which is earliest in time, relative to other channels
% last_delays = 2*maxlag*ones(1,Nchan)+1;
last_maxes = zeros(1,Nchan);
[chan_corr_peak_maxes, chan_corr_peak_locs] = max(chan_CC, [], 1);
best_peak_locs = 2*maxlag*ones(1,Nchan)+1; % initialize to maxlag+1, so 
for iChan = 1:Nchan
    these_maxes = chan_corr_peak_maxes(Nchan*(iChan-1)+1:Nchan*iChan);
    if all(isnan(these_maxes))
        continue; % skip this channel if all correlations are NaN, i.e. zeroed out data
    elseif any(isnan(these_maxes))
        this_chan_corr_peak_locs = chan_corr_peak_locs(Nchan*(iChan-1)+1:Nchan*iChan);
        this_chan_corr_peak_locs(isnan(these_maxes)) = maxlag+1; % set NaN locations to maxlag+1
        chan_corr_peak_locs(Nchan*(iChan-1)+1:Nchan*iChan) = this_chan_corr_peak_locs;
        these_maxes(isnan(these_maxes)) = 0; % set NaNs to zero
    else       
        this_chan_corr_peak_locs = chan_corr_peak_locs(Nchan*(iChan-1)+1:Nchan*iChan);
    end
    % these_delays = this_chan_corr_peak_locs - maxlag - 1;
    if sum(these_maxes) > sum(last_maxes) % if these delays produce higher correlation
        best_peak_locs = this_chan_corr_peak_locs;
        last_maxes = these_maxes;
    end
end
% remove nan values for display
chan_corr_peak_maxes(isnan(chan_corr_peak_maxes)) = 0;
% use the earliest channel as a reference to compute delays
channelDelays = gather(best_peak_locs - maxlag - 1); % -1 because of zero-lag
disp("Channel delays with best correlation computed for all channel combinations: ")
disp(reshape(chan_corr_peak_locs, Nchan, Nchan)-maxlag-1)
disp("Using channel delays with best reference channel: ")
disp(channelDelays)

disp("Correlation values trying each reference channel: ")
disp(reshape(chan_corr_peak_maxes, Nchan, Nchan))
disp(" + ___________________________________________________________")
disp(sum(reshape(chan_corr_peak_maxes, Nchan, Nchan)))

disp("Using best reference channel, with maximal correlation: ")
disp(sum(last_maxes))

end

