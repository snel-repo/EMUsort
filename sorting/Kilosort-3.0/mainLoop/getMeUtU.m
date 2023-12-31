function [UtU, maskU, iList] = getMeUtU(iU, iC, mask, Nnearest, Nchan)
    % this function determines if two templates share any channels
    % iU are the channels that each template is assigned to, one main channel per template
    % iC has as column K the list of neigboring channels for channel K
    % mask are the weights assigned for the corresponding neighboring channels
    % in iC (gaussian-decaying)

    Nfilt = numel(iU);

    U = gpuArray.zeros(Nchan, Nfilt, 'single'); % create a sparse matrix with ones if a channel K belongs to a template

    chanFiltIndexes = int32(0:Nchan:(Nchan * Nfilt - 1));
    try % need to retry the below command, sometimes it fails on first try, with:
        % "An unexpected error occurred trying to launch a kernel. The CUDA error was:
        %  invalid argument"
        ix = iC(:, iU) + chanFiltIndexes; % use the template primary channel to obtain its neighboring channels from iC
    catch
        ix = iC(:, iU) + chanFiltIndexes; % use the template primary channel to obtain its neighboring channels from iC
    end
    U(ix) = 1; % use this as an awkward index into U

    UtU = (U' * U) > 0; %  This is a matrix with ones if two templates share any channels, if this is 0, the templates had not pair of channels in common

    maskU = mask(:, iU); % we also return the masks for each template, picked from the corresponding mask of their primary channel

    if nargin > 3 && nargout > 2
        cc = UtU;
        [~, isort] = sort(cc, 1, 'descend'); % sort template pairs in order of how many channels they share
        iList = int32(gpuArray(isort(1:Nnearest, :))); % take the Nnearest templates for each template
    end
