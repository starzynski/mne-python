import numpy as np
from numpy.testing import assert_array_almost_equal

from mne.time_frequency import dpss_windows, multitaper_psd

try:
    import nitime as ni
except ImportError:
    have_nitime = False
else:
    have_nitime = True
nitime_test = np.testing.dec.skipif(not have_nitime, 'nitime not installed')


@nitime_test
def test_dpss_windows():
    """ Test computation of DPSS windows """

    N = 1000
    half_nbw = 4
    Kmax = int(2 * half_nbw)

    dpss, eigs = dpss_windows(N, half_nbw, Kmax, low_bias=False)
    dpss_ni, eigs_ni = ni.algorithms.dpss_windows(N, half_nbw, Kmax)

    assert_array_almost_equal(dpss, dpss_ni)
    assert_array_almost_equal(eigs, eigs_ni)

    dpss, eigs = dpss_windows(N, half_nbw, Kmax, interp_from=200, low_bias=False)
    dpss_ni, eigs_ni = ni.algorithms.dpss_windows(N, half_nbw, Kmax, interp_from=200)

    assert_array_almost_equal(dpss, dpss_ni)
    assert_array_almost_equal(eigs, eigs_ni)


@nitime_test
def test_multitaper_psd():
    """ Test multi-taper PSD computation """

    n_times = 1000
    x = np.random.randn(5, n_times)
    sfreq = 500

    for adaptive, n_jobs in zip((False, True, True), (1, 1, 2)):
        psd, freqs = multitaper_psd(x, sfreq, adaptive=adaptive, n_jobs=n_jobs)
        freqs_ni, psd_ni, _ = ni.algorithms.spectral.multi_taper_psd(x, sfreq,
                              adaptive=adaptive, jackknife=False)

        # for some reason nitime returns n_times + 1 frequency points
        # causing the value at 0 to be different
        assert_array_almost_equal(psd[:, 1:], psd_ni[:, 1:-1], decimal=3)
        assert_array_almost_equal(freqs, freqs_ni[:-1])
