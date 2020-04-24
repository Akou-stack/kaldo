"""
Unit and regression test for the ballistico package.
"""

# Imports
from ballistico.finitedifference import FiniteDifference
from ballistico.conductivity import Conductivity
from ballistico.phonons import Phonons
import ase.units as units
import numpy as np
import pytest

# NOTE: the scope of this fixture needs to be 'function' for these tests to work properly.
@pytest.yield_fixture(scope="function")
def phonons():
    print ("Preparing phonons object.")

    # Create a finite difference object
    finite_difference = FiniteDifference.from_folder(folder='ballistico/tests/si-amorphous', format='eskm')

    # # Create a phonon object
    phonons = Phonons(finite_difference=finite_difference,
                      is_classic=True,
                      temperature=300,
                      third_bandwidth= 0.05 / 4.135,
                      storage='memory')
    return phonons


def test_gaussian_broadening(phonons):
    phonons.broadening_shape='gauss'
    np.testing.assert_approx_equal(phonons.bandwidth[0][250], 3.200066, significant=4)


def test_lorentz_broadening(phonons):
    phonons.broadening_shape='lorentz'
    phonons.is_tf_backend=False
    np.testing.assert_approx_equal(phonons.bandwidth[0][250], 3.358182, significant=4)


def test_triangle_broadening(phonons):
    phonons.broadening_shape='triangle'
    np.testing.assert_approx_equal(phonons.bandwidth[0][250], 3.358182, significant=4)