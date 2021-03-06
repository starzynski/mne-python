"""
======================================
Export Epochs to a data frame in Pandas
======================================

Short Pandas Primer
----------------------------

Pandas Data Frames
~~~~~~~~~~~~~~~~~~
A data frame can be thought of as a product between a matrix, a list and a dict:
It understands linear algebra and element-wise operations but is size mutable
and allows for labeled access to its data. In addition, the pandas data frame
class provides many useful methods for restructuring, reshaping and visualizing
data. As most methods return data frame instances operations can be chained
with ease which allows to write efficient one-liners.
Taken together, these features qualify data frames for interoperation with
databases and for interactive data exploration / analysis.
Additionally, pandas interfaces with the R statistical computing language that
covers a huge amount of statistical functionality.

Export Options
~~~~~~~~~~~~~~
The pandas exporter comes with two options: either a data frame is returned or
a panel object.

The data frame comes with a hierarchical index, that is an array of unique
tuples (epochs * time slices). This allows to map the higher
dimensional MEG data onto a 2D data table. The column names are the
channel names from the epoch object. The channels can be accessed like entries
of a dictionary:

    epochs_df['MEG 2333']

Epochs and time slices can be accessed with the .ix method:

    epochs_df.ix['epoch 1', 2]['MEG 2333']

The panel object is a collection of non-hierarchically indexed data frames
representing the epochs which can be accessed like entries in a dictionary:

    epochs_df['epoch 1']

This returns a data frame with time slices as rows and channels as columns.

Instance Methods
~~~~~~~~~~~~~~~~
Most numpy methods and many ufuncs can be found as instance methods, e.g.
mean, median, var, std, mul, etc. Below an incomplete listing of additional
useful data frame instance methods:

apply : apply function to data.
    Any kind of custom function can be applied to the data. In combination with
    lambda this can be very useful.
describe : quickly generate summary stats
    Very useful for exploring data.
groupby : generate subgroups and initialize a 'split-apply-combine' operation.
    Creates a group object. Subsequently, methods like apply, agg, or transform
    can be used to manipulate the underlying data separately but simultaneously.
    Finally reset_index can be used to combine the results back into a data
    frame.
plot : wrapper around plt.plot
    However it comes with some special options. For examples see below.
shape : shape attribute
    gets the dimensions of the data frame.

Reference
~~~~~~~~~
More information and additional introductory materials can be found at the pandas
doc sites: http://pandas.pydata.org/pandas-docs/stable/
"""
# Author: Denis Engemann <d.engemann@fz-juelich.de>
#
# License: BSD (3-clause)

print __doc__

import mne
import pylab as pl
import numpy as np
from mne.fiff import Raw
from mne.datasets import sample

from pandas.stats.api import rolling_mean

# turn on interactive mode
pl.ion()

data_path = sample.data_path('..')
raw_fname = data_path + '/MEG/sample/sample_audvis_filt-0-40_raw.fif'

raw = Raw(raw_fname)
events = mne.find_events(raw, stim_channel='STI 014')
raw.info['bads'] = ['MEG 2443', 'EEG 053']
picks = mne.fiff.pick_types(raw.info, meg='grad', eeg=True, eog=True,
                            stim=False, exclude=raw.info['bads'])

tmin, tmax, event_id = -0.2, 0.5, 1
baseline = (None, 0)
reject = dict(grad=4000e-13, eog=150e-6)

epochs = mne.Epochs(raw, events, event_id, tmin, tmax, proj=True, picks=picks,
                    baseline=baseline, preload=False, reject=reject)

epochs_df = epochs.as_data_frame()

meg_chs = [c for c in epochs.ch_names if c.startswith("MEG")]

# display some channels.
epochs_df.ix['epoch 11', :4].head(20)

# plot single epoch.
epochs_df.ix['epoch 11'].plot(legend=False, xlim=(0, 105), title='epoch 11')

# split by timeslices using hierarchical index.
grouped_tsl = epochs_df[meg_chs].groupby(level='time slices')

# then apply mean to each group and create a plot.
grouped_tsl.mean().plot(legend=0, title='MEG average', xlim=(0, 105))

# apply arbitrary numpy function.
grouped_tsl.agg(np.std).plot(legend=0, title='MEG std', xlim=(0, 105))

# smooth using a rolling mean then average and finally plot.
grouped_tsl.apply(lambda x: rolling_mean(x.mean(), 10)).plot(legend=False,
                                                             xlim=(0, 105))

# apply individual functions to channels.
grouped_tsl.agg({"MEG 0113": np.mean, "MEG 0213": np.median})

# investigate epochs using hierarchical index.
grouped_epochs = epochs_df[meg_chs].groupby(level='epochs')

subgroup = grouped_epochs.max().ix['epoch 1':'epoch 12']

subgroup.plot(kind='barh', legend=0)

# create string table for dumping into file.
result_table = subgroup.to_string()

# investigate a specific channel's std across epochs.
chn = "MEG 0113"
grouped_epochs.std()[chn].plot(title=chn, xlim=(0, 55))
