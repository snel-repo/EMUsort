% mexGPUall. For these to complete succesfully, you need to configure the
% Matlab GPU library first (see README files for platform-specific
% information)

% Only compile mex files used for Kilosort-3.0:
%%% -> spikedetector3PC.cu,
%%% -> mexMPnu8.cu/mexMPnu8_pcTight.cu
%%% -> mexWtW2.cu

    enableStableMode = true;
    
    % mexcuda -largeArrayDims spikedetector3.cu
    mexcuda -largeArrayDims spikedetector3PC.cu
    % mexcuda -largeArrayDims mexThSpkPC.cu
    % mexcuda -largeArrayDims mexGetSpikes2.cu
    
    if enableStableMode
        % For algorithm development purposes which require guaranteed
        % deterministic calculations, add -DENSURE_DETERM swtich to
        % compile line for mexMPnu8.cu. -DENABLE_STABLEMODE must also
        % be specified. This version will run ~2X slower than the
        % non deterministic version.
        % mexcuda -largeArrayDims -dynamic -DENABLE_STABLEMODE mexMPnu8.cu
        mexcuda -largeArrayDims -dynamic -DENABLE_STABLEMODE mexMPnu8_pcTight.cu
    else
        % mexcuda -largeArrayDims mexMPnu8.cu
        mexcuda -largeArrayDims mexMPnu8_pcTight.cu
    end

    % mexcuda -largeArrayDims mexSVDsmall2.cu
    mexcuda -largeArrayDims mexWtW2.cu
    % mexcuda -largeArrayDims mexFilterPCs.cu
    % mexcuda -largeArrayDims mexClustering2.cu
    % mexcuda -largeArrayDims mexDistances2.cu


%    mex -largeArrayDims mexMPmuFEAT.cu
%    mex -largeArrayDims mexMPregMU.cu
%    mex -largeArrayDims mexWtW2.cu

% If you get uninterpretable errors, run again with verbose option -v, i.e. mexcuda -v largeArrayDims mexGetSpikes2.cu


