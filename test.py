import numpy as np
import pandas as pd
import ballistico.atoms_helper as ath

import ballistico.geometry_helper as ghl
from ballistico.Phonons import Phonons
from ballistico.MolecularSystem import MolecularSystem
from ballistico.PlotViewController import PlotViewController
from ballistico.ShengbteHelper import ShengbteHelper
from ballistico.interpolation_controller import interpolator
from ballistico.constants import *

import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from sparse import COO
from scipy.sparse import save_npz, load_npz


def plot_file(filename, is_classic=False):
	if is_classic:
		column_id = 2
	else:
		column_id = 1
	data = pd.read_csv (filename, delim_whitespace=True, skiprows=[0, 1], header=None)
	data = np.array (data.values)
	freqs_to_plot = data[:, 0]
	gamma_to_plot = data[:, column_id]
	plt.scatter (freqs_to_plot, gamma_to_plot, marker='.', color='red')


def import_dynamical_matrix(replicas):
	dynamical_matrix_file = 'Dyn.form'
	dynamical_matrix_frame = pd.read_csv (dynamical_matrix_file, header=None, delim_whitespace=True)
	dynamical_matrix_vector = dynamical_matrix_frame.values
	n_replicas = replicas[0] * replicas[1] * replicas[2]
	n_particles = int ((dynamical_matrix_vector.size / (3. ** 2.)) ** (1. / 2.) / n_replicas)
	return dynamical_matrix_vector.reshape (n_replicas, n_particles, 3, n_replicas, n_particles, 3)


def import_third_order(ndim):
	third_order_frame = pd.read_csv ('THIRD', header=None, delim_whitespace=True)
	third_order = third_order_frame.values.T
	v3ijk = third_order[5:8].T
	n_particles = int (ndim / 3)
	coords = np.vstack ((third_order[0:5] - 1, 0 * np.ones ((third_order.shape[1]))))
	sparse_x = COO (coords, v3ijk[:, 0], shape=(n_particles, 3, n_particles, 3, n_particles, 3))
	coords = np.vstack ((third_order[0:5] - 1, 1 * np.ones ((third_order.shape[1]))))
	sparse_y = COO (coords, v3ijk[:, 1], shape=(n_particles, 3, n_particles, 3, n_particles, 3))
	coords = np.vstack ((third_order[0:5] - 1, 2 * np.ones ((third_order.shape[1]))))
	sparse_z = COO (coords, v3ijk[:, 2], shape=(n_particles, 3, n_particles, 3, n_particles, 3))
	sparse = sparse_x + sparse_y + sparse_z
	return sparse.reshape ((ndim, ndim, ndim))


def specific_heat(omega_i, temperature):
	x = hbar * omega_i / (2 * k_b * temperature)
	return k_b * (x / np.sinh (x)) ** 2


def diffusivity(omega, i, volume):
	prefactor = np.pi * volume ** 2 / (3 * hbar ** 2 * omega[i] ** 2)


def conductivity(temperature, i):
	pass


if __name__ == "__main__":
	is_classic = True
	sigma = 0.05
	
	print ('sigma', sigma)
	
	geometry = ath.from_filename ('reference.xyz')
	# forcefield = ["pair_style tersoff", "pair_coeff * * forcefields/Si.tersoff Si"]
	
	replicas = np.array ([1, 1, 1])
	raw_system = MolecularSystem (geometry, replicas=replicas, temperature=300., optimize=False, lammps_cmd=None)
	n_phonons = raw_system.configuration.get_positions ().shape[0] * 3
	
	raw_system.dynamical_matrix = import_dynamical_matrix (raw_system.replicas)
	
	print ('second order loaded')
	raw_system.third_order = import_third_order (n_phonons)
	
	print ('third order loaded')
	
	system = Phonons (raw_system, np.array ([1, 1, 1]), is_classic=is_classic)
	freqs_to_plot = system.frequencies.flatten ()
	
	# ph = MolecularSystemPhonons (system, np.array ([1, 1, 1]))
	# ph.calculate_second_all_grid()
	
	plt.plot (freqs_to_plot)
	
	plt.ylabel ('$\\nu$/THz', fontsize='14', fontweight='bold')
	plt.xlabel ("phonon id", fontsize='14', fontweight='bold')
	plt.show ()
	
	in_ph = 3
	n_phonons = freqs_to_plot.shape[0]
	
	gamma_plus = np.zeros (n_phonons)
	gamma_minus = np.zeros (n_phonons)
	file = open ("Decay.ballistico", "w+")
	
	for index_phonons in range (in_ph, n_phonons):
		gamma_plus[index_phonons], gamma_minus[index_phonons] = system.calculate_single_gamma (sigma, index_phonons,
		                                                                                       in_ph)
		
		hbar = 6.35075751
		
		gamma_to_plot = (gamma_plus + gamma_minus)
		print (index_phonons, freqs_to_plot[index_phonons], gamma_plus[index_phonons])
		file.write (str (index_phonons) + ', ' + str (freqs_to_plot[index_phonons]) + ', ' + str (
			gamma_to_plot[index_phonons]))
		
		plt.scatter (freqs_to_plot[in_ph:index_phonons], gamma_to_plot[in_ph:index_phonons])
		plt.ylim ([0, 5])
		plt.xlabel ('$\\nu$/THz', fontsize='14', fontweight='bold')
		plt.ylabel ("$2\Gamma$/meV", fontsize='14', fontweight='bold')
		for i in range (1):
			plot_file ('Decay.' + str (i), is_classic=is_classic)
		
		plt.show ()
	file.close ()
	print ('End of calculations')