from sklearn.model_selection import ParameterGrid


# Define the parameter grid to be searched over using ops variables from Kilosort_config_3.m
# All parameter combinations are tried, so be careful to consider the total number of combinations,
# which is the product of the numbers of elements in each dictionary element.
#
# uncomment the parameters for the search scheme you want to use, and which number of combinations
#
# Th = threshold of similarity during PCA projection to be considered in the cluster, second element
#      is for the final pass, and should be lower
# spkTh = amplitude threshold for detecting spikes during initialization of 1D templates. Multiple
#         values will run multiple passes, and collect all spikes for consideration to be used for
#         initial templates, ignoring duplicates. (KS default is -6, did not allow multiple values)
def get_params_grid():
    grid = dict(
        # Search Schemes:
        ###########################################################################################
        ## v 12 combinations, standard choice
        # Th=[[10, 4], [7, 3], [5, 2], [2, 1]],
        # spkTh=[[-6], [-3, -6], [-6, -9]],
        ## ^
        ###########################################################################################
        ## v 8 combinations, less comprehensive search
        # Th=[[10, 4], [7, 3], [5, 2], [2, 1]],
        # spkTh=[[-6], [-3, -6]],
        ## ^
        ###########################################################################################
        ## v 16 combinations, more comprehensive Th search
        # Th=[[10, 4], [10, 2], [8, 2], [7, 2], [6, 2], [5, 2], [4, 2], [3, 1]],
        # spkTh=[[-6], [-3, -6]],
        ## ^
        ###########################################################################################
        ## v 16 combinations, more comprehensive spkTh search
        Th=[[10, 4], [7, 3], [5, 2], [2, 1]],
        spkTh=[[-3], [-6], [-3, -6], [-6, -9]],
        ## ^
        ###########################################################################################
        ## v 24 combinations, most comprehensive search
        # Th=[[10, 4], [10, 2], [8, 2], [7, 2], [6, 2], [5, 2], [4, 2], [3, 1]],
        # spkTh=[[-6], [-3, -6], [-6, -9]],
        ## ^
        ###########################################################################################
        ## v 15 combinations, more comprehensive combination of spike thresholds for template init
        # Th=[[10, 4], [8, 4], [7, 3], [5, 2], [2, 1]],
        # spkTh=[[-6], [-3, -6], [-6, -9]],
        ## ^
        ###########################################################################################
        ## v 12 combinations, low thresholds (for getting small spikes)
        # Th=[[6, 3], [5, 2], [3, 1], [2, 1]],
        # spkTh=[[-2], [-6], [-2, -6]],
        ## ^
        ###########################################################################################
        ## v 12 combinations, higher thresholds and similarity requirements (for getting big spikes)
        # Th=[[12, 6], [10, 4], [8, 4], [6, 3]],
        # spkTh=[[-6], [-9], [-6, -9]],
        ## ^
        ###########################################################################################
        ## v 8 combinations, wide PCA similarity range (lower means clusters more liberally combined)
        # Th=[[10, 4], [7, 3], [5, 2.5], [4, 2], [3, 1.5], [2, 1], [1.5, 0.75], [1, 0.5]],
        ## ^
        ###########################################################################################
        ## v or Make your own!
        #
        #
        ## ^
        ###########################################################################################
        ## other parameters, experimental use, not really recommended
        # lam=[10, 15],
        # long_range=[[30, 3], [30, 1]],
        # nfilt_factor=[12, 4],
        # AUCsplit=[0.8, 0.9],
        # momentum=[[20, 400], [60, 600]],
    )
    return ParameterGrid(grid)
