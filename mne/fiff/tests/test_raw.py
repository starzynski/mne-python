# Author: Alexandre Gramfort <gramfort@nmr.mgh.harvard.edu>
#         Denis Engemann <d.engemann@fz-juelich.de>
#
# License: BSD (3-clause)

import os.path as op
from copy import deepcopy
import warnings

import numpy as np
from numpy.testing import assert_array_almost_equal, assert_array_equal
from nose.tools import assert_true, assert_raises, assert_equal

from mne.fiff import Raw, pick_types, pick_channels, concatenate_raws
from mne import concatenate_events, find_events

try:
    import nitime
except ImportError:
    have_nitime = False
else:
    have_nitime = True
nitime_test = np.testing.dec.skipif(not have_nitime, 'nitime not installed')

base_dir = op.join(op.dirname(__file__), 'data')
fif_fname = op.join(base_dir, 'test_raw.fif')
fif_gz_fname = op.join(base_dir, 'test_raw.fif.gz')
ctf_fname = op.join(base_dir, 'test_ctf_raw.fif')
fif_bad_marked_fname = op.join(base_dir, 'test_withbads_raw.fif')
bad_file_works = op.join(base_dir, 'test_bads.txt')
bad_file_wrong = op.join(base_dir, 'test_wrong_bads.txt')


def test_multiple_files():
    """Test loading multiple files simultaneously
    """

    # split file
    raw = Raw(fif_fname, preload=True)
    split_size = 10.  # in seconds
    sfreq = raw.info['sfreq']
    nsamp = (raw.last_samp - raw.first_samp)
    tmins = np.round(np.arange(0., nsamp, split_size * sfreq))
    tmaxs = np.concatenate((tmins[1:] - 1, [nsamp]))
    tmaxs /= sfreq
    tmins /= sfreq

    # going in revere order so the last fname is the first file (need it later)
    raws = [None] * len(tmins)
    for ri in range(len(tmins) - 1, -1, -1):
        fname = 'test_raw_split-%d_raw.fif' % ri
        raw.save(fname, tmin=tmins[ri], tmax=tmaxs[ri])
        raws[ri] = Raw(fname)
    events = [find_events(r) for r in raws]
    last_samps = [r.last_samp for r in raws]
    first_samps = [r.first_samp for r in raws]

    # test concatenation of split file
    all_raw_1 = concatenate_raws(raws, preload=False)
    assert_true(raw.first_samp == all_raw_1.first_samp)
    assert_true(raw.last_samp == all_raw_1.last_samp)
    assert_array_almost_equal(raw[:, :][0], all_raw_1[:, :][0])
    raws[0] = Raw(fname)
    all_raw_2 = concatenate_raws(raws, preload=True)
    assert_array_almost_equal(raw[:, :][0], all_raw_2[:, :][0])

    # test proper event treatment for split files
    events = concatenate_events(events, first_samps, last_samps)
    events2 = find_events(all_raw_2)
    assert_array_equal(events, events2)

    # test various methods of combining files
    n_combos = 9
    raw_combos = [None] * n_combos

    raw = Raw(fif_fname, preload=True)
    raw_combos[0] = Raw([fif_fname, fif_fname], preload=True)
    raw_combos[1] = Raw([fif_fname, fif_fname], preload=False)
    raw_combos[2] = Raw([fif_fname, fif_fname], preload='memmap8.dat')
    assert_raises(ValueError, Raw, [fif_fname, ctf_fname])
    assert_raises(ValueError, Raw, [fif_fname, fif_bad_marked_fname])
    n_times = len(raw._times)
    assert_true(raw[:, :][0].shape[1] * 2 == raw_combos[0][:, :][0].shape[1])
    assert_true(raw_combos[0][:, :][0].shape[1] == len(raw_combos[0]._times))

    # with all data preloaded, result should be preloaded
    raw_combos[3] = Raw(fif_fname, preload=True)
    raw_combos[3].append(Raw(fif_fname, preload=True))
    assert_true(raw_combos[0]._preloaded == True)

    # with any data not preloaded, don't set result as preloaded
    raw_combos[4] = concatenate_raws([Raw(fif_fname, preload=True),
                                      Raw(fif_fname, preload=False)])
    assert_true(raw_combos[1]._preloaded == False)
    assert_array_equal(find_events(raw_combos[4]), find_events(raw_combos[0]))

    # user should be able to force data to be preloaded upon concat
    raw_combos[5] = concatenate_raws([Raw(fif_fname, preload=False),
                                      Raw(fif_fname, preload=True)],
                                     preload=True)
    assert_true(raw_combos[2]._preloaded == True)

    raw_combos[6] = concatenate_raws([Raw(fif_fname, preload=False),
                                      Raw(fif_fname, preload=True)],
                                     preload='memmap3.dat')

    raw_combos[7] = concatenate_raws([Raw(fif_fname, preload=True),
                                      Raw(fif_fname, preload=True)],
                                     preload='memmap4.dat')

    raw_combos[8] = concatenate_raws([Raw(fif_fname, preload=False),
                                      Raw(fif_fname, preload=False)],
                                     preload='memmap5.dat')

    # make sure that all our data match
    times = range(0, 2 * n_times, 999)
    # add potentially problematic points
    times.extend([n_times - 1, n_times, 2 * n_times - 1])
    for ti in times:  # let's do a subset of points for speed
        orig = raw[:, ti % n_times][0]
        for raw_combo in raw_combos:
            # these are almost_equals because of possible dtype differences
            assert_array_almost_equal(orig, raw_combo[:, ti][0])

    # verify that combining raws with different projectors throws an exception
    raw.add_proj([], remove_existing=True)
    assert_raises(ValueError, raw.append, Raw(fif_fname, preload=True))

    # now test event treatment for concatenated raw files
    events = [find_events(raw), find_events(raw)]
    last_samps = [raw.last_samp, raw.last_samp]
    first_samps = [raw.first_samp, raw.first_samp]
    events = concatenate_events(events, first_samps, last_samps)
    events2 = find_events(raw_combos[0])
    assert_array_equal(events, events2)

    # check out the len method
    assert_true(len(raw) == raw.n_times)
    assert_true(len(raw) == raw.last_samp - raw.first_samp + 1)


def test_load_bad_channels():
    """Test reading/writing of bad channels
    """

    # Load correctly marked file (manually done in mne_process_raw)
    raw_marked = Raw(fif_bad_marked_fname)
    correct_bads = raw_marked.info['bads']
    raw = Raw(fif_fname)
    # Make sure it starts clean
    assert_array_equal(raw.info['bads'], [])

    # Test normal case
    raw.load_bad_channels(bad_file_works)
    # Write it out, read it in, and check
    raw.save('foo_raw.fif')
    raw_new = Raw('foo_raw.fif')
    assert_equal(correct_bads, raw_new.info['bads'])
    # Reset it
    raw.info['bads'] = []

    # Test bad case
    assert_raises(ValueError, raw.load_bad_channels, bad_file_wrong)

    # Test forcing the bad case
    with warnings.catch_warnings(record=True) as w:
        raw.load_bad_channels(bad_file_wrong, force=True)
        assert_equal(len(w), 1)
        # write it out, read it in, and check
        raw.save('foo_raw.fif')
        raw_new = Raw('foo_raw.fif')
        assert_equal(correct_bads, raw_new.info['bads'])

    # Check that bad channels are cleared
    raw.load_bad_channels(None)
    raw.save('foo_raw.fif')
    raw_new = Raw('foo_raw.fif')
    assert_equal([], raw_new.info['bads'])


def test_io_raw():
    """Test IO for raw data (Neuromag + CTF + gz)
    """
    fnames_in = [fif_fname, fif_gz_fname, ctf_fname]
    fnames_out = ['raw.fif', 'raw.fif.gz', 'raw.fif']
    for fname_in, fname_out in zip(fnames_in, fnames_out):
        raw = Raw(fname_in)

        nchan = raw.info['nchan']
        ch_names = raw.info['ch_names']
        meg_channels_idx = [k for k in range(nchan)
                            if ch_names[k][0] == 'M']
        n_channels = 100
        meg_channels_idx = meg_channels_idx[:n_channels]
        start, stop = raw.time_as_index([0, 5])
        data, times = raw[meg_channels_idx, start:(stop + 1)]
        meg_ch_names = [ch_names[k] for k in meg_channels_idx]

        # Set up pick list: MEG + STI 014 - bad channels
        include = ['STI 014']
        include += meg_ch_names
        picks = pick_types(raw.info, meg=True, eeg=False,
                           stim=True, misc=True, include=include,
                           exclude=raw.info['bads'])
        print "Number of picked channels : %d" % len(picks)

        # Writing with drop_small_buffer True
        raw.save(fname_out, picks, tmin=0, tmax=4, buffer_size_sec=3,
                 drop_small_buffer=True)
        raw2 = Raw(fname_out, preload=True)

        sel = pick_channels(raw2.ch_names, meg_ch_names)
        data2, times2 = raw2[sel, :]
        assert_true(times2.max() <= 3)

        # Writing
        raw.save(fname_out, picks, tmin=0, tmax=5)

        if fname_in == fif_fname or fname_in == fif_fname + '.gz':
            assert_true(len(raw.info['dig']) == 146)

        raw2 = Raw(fname_out)

        sel = pick_channels(raw2.ch_names, meg_ch_names)
        data2, times2 = raw2[sel, :]

        assert_array_almost_equal(data, data2)
        assert_array_almost_equal(times, times2)
        assert_array_almost_equal(raw.info['dev_head_t']['trans'],
                                  raw2.info['dev_head_t']['trans'])
        assert_array_almost_equal(raw.info['sfreq'], raw2.info['sfreq'])

        if fname_in == fif_fname or fname_in == fif_fname + '.gz':
            assert_array_almost_equal(raw.info['dig'][0]['r'],
                                      raw2.info['dig'][0]['r'])


def test_io_complex():
    """Test IO with complex data types
    """
    dtypes = [np.complex64, np.complex128]

    raw = Raw(fif_fname, preload=True)
    picks = np.arange(5)
    start, stop = raw.time_as_index([0, 5])

    data_orig, _ = raw[picks, start:stop]

    for di, dtype in enumerate(dtypes):
        imag_rand = np.array(1j * np.random.randn(data_orig.shape[0],
                             data_orig.shape[1]), dtype)

        raw_cp = deepcopy(raw)
        raw_cp._data = np.array(raw_cp._data, dtype)
        raw_cp._data[picks, start:stop] += imag_rand
        # this should throw an error because it's complex
        with warnings.catch_warnings(record=True) as w:
            raw_cp.save('raw.fif', picks, tmin=0, tmax=5)
            # warning only gets thrown on first instance
            assert_equal(len(w), 1 if di == 0 else 0)

        raw2 = Raw('raw.fif')
        raw2_data, _ = raw2[picks, :]
        n_samp = raw2_data.shape[1]
        assert_array_almost_equal(raw2_data[:, :n_samp],
                                  raw_cp._data[picks, :n_samp])
        # with preloading
        raw2 = Raw('raw.fif', preload=True)
        raw2_data, _ = raw2[picks, :]
        n_samp = raw2_data.shape[1]
        assert_array_almost_equal(raw2_data[:, :n_samp],
                                  raw_cp._data[picks, :n_samp])


def test_getitem():
    """Test getitem/indexing of Raw
    """
    for preload in [False, True, 'memmap.dat']:
        raw = Raw(fif_fname, preload=preload)
        data, times = raw[0, :]
        data1, times1 = raw[0]
        assert_array_equal(data, data1)
        assert_array_equal(times, times1)
        data, times = raw[0:2, :]
        data1, times1 = raw[0:2]
        assert_array_equal(data, data1)
        assert_array_equal(times, times1)
        data1, times1 = raw[[0, 1]]
        assert_array_equal(data, data1)
        assert_array_equal(times, times1)


def test_proj():
    """Test SSP proj operations
    """
    for proj_active in [True, False]:
        raw = Raw(fif_fname, preload=False, proj_active=proj_active)
        assert_true(all(p['active'] == proj_active for p in raw.info['projs']))

        data, times = raw[0:2, :]
        data1, times1 = raw[0:2]
        assert_array_equal(data, data1)
        assert_array_equal(times, times1)

        # test adding / deleting proj
        if proj_active:
            assert_raises(ValueError, raw.add_proj, [],
                          {'remove_existing': True})
            assert_raises(ValueError, raw.del_proj, 0)
        else:
            projs = deepcopy(raw.info['projs'])
            n_proj = len(raw.info['projs'])
            raw.del_proj(0)
            assert_true(len(raw.info['projs']) == n_proj - 1)
            raw.add_proj(projs, remove_existing=False)
            assert_true(len(raw.info['projs']) == 2 * n_proj - 1)
            raw.add_proj(projs, remove_existing=True)
            assert_true(len(raw.info['projs']) == n_proj)

    # test apply_proj() with and without preload
    for preload in [True, False]:
        raw = Raw(fif_fname, preload=preload, proj_active=False)
        data, times = raw[:, 0:2]
        raw.apply_projector()
        data_proj_1 = np.dot(raw._projector, data)

        # load the file again without proj
        raw = Raw(fif_fname, preload=preload, proj_active=False)

        # write the file with proj. activated, make sure proj has been applied
        raw.save('raw.fif', proj_active=True)
        raw2 = Raw('raw.fif', proj_active=False)
        data_proj_2, _ = raw2[:, 0:2]
        assert_array_almost_equal(data_proj_1, data_proj_2)
        assert_true(all(p['active'] for p in raw2.info['projs']))

        # read orig file with proj. active
        raw2 = Raw(fif_fname, preload=preload, proj_active=True)
        data_proj_2, _ = raw2[:, 0:2]
        assert_array_almost_equal(data_proj_1, data_proj_2)
        assert_true(all(p['active'] for p in raw2.info['projs']))

        # test that apply_projector works
        raw.apply_projector()
        data_proj_2, _ = raw[:, 0:2]
        assert_array_almost_equal(data_proj_1, data_proj_2)
        assert_array_almost_equal(data_proj_2,
                                  np.dot(raw._projector, data_proj_2))


def test_preload_modify():
    """ Test preloading and modifying data
    """
    for preload in [False, True, 'memmap.dat']:
        raw = Raw(fif_fname, preload=preload)

        nsamp = raw.last_samp - raw.first_samp + 1
        picks = pick_types(raw.info, meg='grad')

        data = np.random.randn(len(picks), nsamp / 2)

        try:
            raw[picks, :nsamp / 2] = data
        except RuntimeError as err:
            if not preload:
                continue
            else:
                raise err

        tmp_fname = 'raw.fif'
        raw.save(tmp_fname)

        raw_new = Raw(tmp_fname)
        data_new, _ = raw_new[picks, :nsamp / 2]

        assert_array_almost_equal(data, data_new)


def test_filter():
    """ Test filtering and Raw.apply_function interface """

    raw = Raw(fif_fname, preload=True)
    picks_meg = pick_types(raw.info, meg=True)
    picks = picks_meg[:4]

    raw_lp = deepcopy(raw)
    raw_lp.filter(0., 4.0, picks=picks, n_jobs=2)

    raw_hp = deepcopy(raw)
    raw_lp.filter(8.0, None, picks=picks, n_jobs=2)

    raw_bp = deepcopy(raw)
    raw_bp.filter(4.0, 8.0, picks=picks)

    data, _ = raw[picks, :]

    lp_data, _ = raw_lp[picks, :]
    hp_data, _ = raw_hp[picks, :]
    bp_data, _ = raw_bp[picks, :]

    assert_array_almost_equal(data, lp_data + hp_data + bp_data)

    # make sure we didn't touch other channels
    data, _ = raw[picks_meg[4:], :]
    bp_data, _ = raw_bp[picks_meg[4:], :]

    assert_array_equal(data, bp_data)


def test_hilbert():
    """ Test computation of analytic signal using hilbert """
    raw = Raw(fif_fname, preload=True)
    picks_meg = pick_types(raw.info, meg=True)
    picks = picks_meg[:4]

    raw2 = deepcopy(raw)
    raw.apply_hilbert(picks)
    raw2.apply_hilbert(picks, envelope=True, n_jobs=2)

    env = np.abs(raw._data[picks, :])
    assert_array_almost_equal(env, raw2._data[picks, :])


def test_raw_copy():
    """ Test Raw copy"""
    raw = Raw(fif_fname, preload=True)
    data, _ = raw[:, :]
    copied = raw.copy()
    copied_data, _ = copied[:, :]
    assert_array_equal(data, copied_data)
    assert_equal(sorted(raw.__dict__.keys()),
                 sorted(copied.__dict__.keys()))

    raw = Raw(fif_fname, preload=False)
    data, _ = raw[:, :]
    copied = raw.copy()
    copied_data, _ = copied[:, :]
    assert_array_equal(data, copied_data)
    assert_equal(sorted(raw.__dict__.keys()),
                 sorted(copied.__dict__.keys()))


@nitime_test
def test_raw_to_nitime():
    """ Test nitime export """
    raw = Raw(fif_fname, preload=True)
    picks_meg = pick_types(raw.info, meg=True)
    picks = picks_meg[:4]
    raw_ts = raw.to_nitime(picks=picks)
    assert_true(raw_ts.data.shape[0] == len(picks))

    raw = Raw(fif_fname, preload=False)
    picks_meg = pick_types(raw.info, meg=True)
    picks = picks_meg[:4]
    raw_ts = raw.to_nitime(picks=picks)
    assert_true(raw_ts.data.shape[0] == len(picks))

    raw = Raw(fif_fname, preload=True)
    picks_meg = pick_types(raw.info, meg=True)
    picks = picks_meg[:4]
    raw_ts = raw.to_nitime(picks=picks, copy=False)
    assert_true(raw_ts.data.shape[0] == len(picks))

    raw = Raw(fif_fname, preload=False)
    picks_meg = pick_types(raw.info, meg=True)
    picks = picks_meg[:4]
    raw_ts = raw.to_nitime(picks=picks, copy=False)
    assert_true(raw_ts.data.shape[0] == len(picks))


def test_raw_index_as_time():
    """ Test index as time conversion"""
    raw = Raw(fif_fname, preload=True)
    t0 = raw.index_as_time([0], True)[0]
    t1 = raw.index_as_time([100], False)[0]
    t2 = raw.index_as_time([100], True)[0]
    assert_true((t2 - t1) == t0)


def test_raw_time_as_index():
    """ Test index as time conversion"""
    raw = Raw(fif_fname, preload=True)
    first_samp = raw.time_as_index([0], True)[0]
    assert_true(raw.first_samp == first_samp)
