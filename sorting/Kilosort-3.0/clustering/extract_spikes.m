function [rez, st3, tF] = extract_spikes(rez)

    % get the electrode position boundaries
    ymin = min(rez.yc);
    ymax = max(rez.yc);
    xmin = min(rez.xc);
    xmax = max(rez.xc);

    % dmin = median(diff(unique(rez.yc)));
    % fprintf('vertical pitch size is %d \n', dmin)
    % rez.ops.dmin = dmin;
    % rez.ops.yup = ymin:dmin/2:ymax; % centers of the upsampled y positions
    %
    % % dminx = median(diff(unique(rez.xc)));
    % yunq = unique(rez.yc);
    % mxc = zeros(numel(yunq), 1);
    % for j = 1:numel(yunq)
    %     xc = rez.xc(rez.yc==yunq(j));
    %     if numel(xc)>1
    %        mxc(j) = median(diff(sort(xc)));
    %     end
    % end
    % dminx = median(mxc);
    % fprintf('horizontal pitch size is %d \n', dminx)
    %
    % rez.ops.dminx = dminx;
    % nx = round((xmax-xmin) / (dminx/2)) + 1;
    % rez.ops.xup = linspace(xmin, xmax, nx); % centers of the upsampled x positions
    % disp(rez.ops.xup)

    % rez.ops.yup = ymin:10:ymax; % centers of the upsampled y positions
    % rez.ops.xup = xmin +  [-16 0 16 32 48 64]; % centers of the upsampled x positions

    ops = rez.ops;

    spkTh = ops.Th(1);
    sig = 1000; % set microns as hardcoded BASE gaussian kernel radius for the nearest channels
    dNearActiveSite = median(diff(unique(rez.yc)));

    [ycup, xcup] = meshgrid(ops.yup, ops.xup); % define the 2x upsampled grid

    NrankPC = ops.nPCs; %!!

    % [wTEMP, wPCA]    = extractTemplatesfromSnippets(rez, NrankPC);
    wTEMP = rez.wTEMP;
    wPCA = rez.wPCA;
    NchanNear = min(ops.Nchan, 16); % % CHANGED: was 8
    [iC, dist] = getClosestChannels2(ycup, xcup, rez.yc, rez.xc, NchanNear);

    igood = dist(1, :) < dNearActiveSite;
    iC = iC(:, igood);
    dist = dist(:, igood);

    ycup = ycup(igood);
    xcup = xcup(igood);

    NchanNearUp = min(numel(ycup), 10 * NchanNear);
    [iC2, dist2] = getClosestChannels2(ycup, xcup, ycup, xcup, NchanNearUp);

    nsizes = 5;
    v2 = gpuArray.zeros(nsizes, size(dist, 2), 'single');
    for k = 1:nsizes
        v2(k, :) = sum(exp(- 2 * dist .^ 2 / (sig * k) ^ 2), 1);
    end

    NchanUp = size(iC, 2);

    % wTEMP = wPCA * (wPCA' * wTEMP);

    t0 = 0;
    id = [];
    mu = [];
    nsp = 0;

    tF = zeros(NrankPC, NchanNear, 1e6, 'single');

    tic
    st3 = zeros(1000000, 6);

    for k = 1:ops.Nbatch
        dataRAW = get_batch(rez.ops, k);

        Params = [size(dataRAW, 1) ops.Nchan ops.nt0 NchanNear NrankPC ops.nt0min spkTh NchanUp NchanNearUp sig];

        [dat, kkmax, st, cF, feat] = ...
            spikedetector3PC(Params, dataRAW, wTEMP, iC - 1, dist, v2, iC2 - 1, dist2, wPCA);
        %     [dat, kkmax, st, cF] = ...
        %         spikedetector3(Params, dataRAW, wTEMP, iC-1, dist, v2, iC2-1, dist2);

        ns = size(st, 2);
        if nsp + ns > size(tF, 3)
            tF(:, :, end +1e6) = 0;
            st3(end +1e6, 1) = 0;
        end

        toff = ops.nt0min + t0 + ops.NT * (k - 1);
        st(1, :) = st(1, :) + toff;
        st = double(st);
        % https://github.com/MouseLand/Kilosort/issues/427
        try
            st(5, :) = cF;
        catch
            st = [st; cF];
        end
        st(6, :) = k - 1;

        st3(nsp + [1:ns], :) = gather(st)';

        tF(:, :, nsp + [1:ns]) = gather(feat);
        nsp = nsp + ns;

        if rem(k, round(ops.Nbatch / 10)) == 0 % print progress 10 times
            fprintf('%2.2f sec, %d batches, %d spikes \n', toc, k, nsp)
        end
    end
    tF = tF(:, :, 1:nsp); % remove excess preallocated space
    st3 = st3(1:nsp, :);

    rez.iC = iC;
    tF = permute(tF, [3, 1, 2]);

    rez.ycup = ycup;
    rez.xcup = xcup;

end
