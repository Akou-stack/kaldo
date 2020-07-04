"""
kaldo
Anharmonic Lattice Dynamics
"""
import numpy as np
from sparse import COO
from kaldo.grid import wrap_coordinates
from kaldo.controllers.displacement import calculate_second, calculate_third
from kaldo.secondorder import SecondOrder
from kaldo.thirdorder import ThirdOrder
from kaldo.helpers.logger import get_logger
logging = get_logger()

DELTA_SHIFT = 1e-5
MAIN_FOLDER = 'displacement'


class ForceConstants(object):
    """ Class for constructing the finite difference object to calculate
        the second/third order force constant matrices after providing the
        unit cell geometry and calculator information.
    """

    def __init__(self,
                 atoms,
                 supercell=(1, 1, 1),
                 folder=MAIN_FOLDER,
                 distance_threshold=None):

        """Init with an instance of constructed ForceConstant object.

        Parameters:

        atoms: Tabulated xyz files or Atoms object
            The atoms to work on.
        supercell: tuple
            Size of supercell given by the number of repetitions (l, m, n) of
            the small unit cell in each direction
        folder: str
            Name str for the displacement folder
        distance_threshold: float
            the maximum distance between two interacting atoms
        """

        # Store the user defined information to the object
        self.atoms = atoms
        self.supercell = supercell
        self.n_atoms = atoms.positions.shape[0]
        self.n_modes = self.n_atoms * 3
        self.n_replicas = np.prod(supercell)
        self.n_replicated_atoms = self.n_replicas * self.n_atoms
        self.cell_inv = np.linalg.inv(atoms.cell)
        self.folder = folder
        self.distance_threshold = distance_threshold
        self._list_of_replicas = None


    @classmethod
    def from_folder(cls, folder, supercell=(1, 1, 1), format='eskm', third_energy_threshold=0.,
                    distance_threshold=None, is_acoustic_sum=False):
        """
        Create a finite difference object from a folder
        :param folder:
        :param supercell:
        :param format:
        :param third_energy_threshold:
        :param distance_threshold:
        :param third_supercell:
        :param is_acoustic_sum:
        :return:
        """
        second_order = SecondOrder.load(folder=folder, supercell=supercell, format=format, is_acoustic_sum=is_acoustic_sum)
        third_order = ThirdOrder.load(folder=folder, supercell=supercell, format=format, third_energy_threshold=third_energy_threshold)
        atoms = second_order.atoms
        # Create a finite difference object
        forceconstants = {'atoms': atoms,
                             'supercell': supercell,
                             'folder': folder}
        forceconstants = cls(**forceconstants)
        forceconstants.second_order = second_order
        forceconstants.third_order = third_order
        return forceconstants



    def calculate_second(self, calculator, grid_type='C', delta_shift=DELTA_SHIFT):
        # TODO: move to ifc
        atoms = self.atoms
        self.second_order = SecondOrder.from_supercell(atoms,
                                                       supercell=self.supercell,
                                                       grid_type=grid_type,
                                                       is_acoustic_sum=False)
        replicated_atoms = self.second_order.replicated_atoms
        atoms.set_calculator(calculator)
        replicated_atoms.set_calculator(calculator)

        _second_order = calculate_second(atoms,
                                         replicated_atoms,
                                         delta_shift)

        self.second_order.value = _second_order


    def calculate_third(self, calculator, grid_type='C', delta_shift=DELTA_SHIFT, supercell=None):
        if supercell is None:
            supercell = self.supercell
        atoms = self.atoms
        self.third_order = ThirdOrder.from_supercell(atoms,
                                                     supercell=supercell,
                                                     grid_type=grid_type)
        replicated_atoms = self.third_order.replicated_atoms
        atoms.set_calculator(calculator)
        replicated_atoms.set_calculator(calculator)

        _third_order = calculate_third(atoms,
                                       replicated_atoms,
                                       delta_shift,
                                       distance_threshold=self.distance_threshold)
        self.third_order.value = _third_order



    def unfold_third_order(self, reduced_third=None, distance_threshold=None):
        logging.info('Unfolding third order matrix')
        if distance_threshold is None:
            if self.distance_threshold is not None:
                distance_threshold = self.distance_threshold
            else:
                raise ValueError('Please specify a distance threshold in Armstrong')

        logging.info('Distance threshold: ' + str(distance_threshold) + ' A')
        if (self.atoms.cell[0, 0] / 2 < distance_threshold) | \
                (self.atoms.cell[1, 1] / 2 < distance_threshold) | \
                (self.atoms.cell[2, 2] / 2 < distance_threshold):
            logging.warning('The cell size should be at least twice the distance threshold')
        if reduced_third is None:
            reduced_third = self.third_order.value
        n_unit_atoms = self.n_atoms
        atoms = self.atoms
        n_replicas = self.n_replicas
        replicated_cell_inv = np.linalg.inv(self.replicated_atoms.cell)

        reduced_third = reduced_third.reshape(
            (n_unit_atoms, 3, n_replicas, n_unit_atoms, 3, n_replicas, n_unit_atoms, 3))
        replicated_positions = self.replicated_atoms.positions.reshape((n_replicas, n_unit_atoms, 3))
        dxij_reduced = wrap_coordinates(atoms.positions[:, np.newaxis, np.newaxis, :] - replicated_positions[np.newaxis, :, :, :], self.replicated_atoms.cell, replicated_cell_inv)
        indices = np.argwhere(np.linalg.norm(dxij_reduced, axis=-1) < distance_threshold)

        coords = []
        values = []
        for index in indices:
            for l in range(n_replicas):
                for j in range(n_unit_atoms):
                    dx2 = dxij_reduced[index[0], l, j]

                    is_storing = (np.linalg.norm(dx2) < distance_threshold)
                    if is_storing:
                        for alpha in range(3):
                            for beta in range(3):
                                for gamma in range(3):
                                    coords.append([index[0], alpha, index[1], index[2], beta, l, j, gamma])
                                    values.append(reduced_third[index[0], alpha, 0, index[2], beta, 0, j, gamma])
                                    
                                    
        logging.info('Created unfolded third order')

        shape = (n_unit_atoms, 3, n_replicas, n_unit_atoms, 3, n_replicas, n_unit_atoms, 3)
        expanded_third = COO(np.array(coords).T, np.array(values), shape)
        expanded_third = expanded_third.reshape(
            (n_unit_atoms * 3, n_replicas * n_unit_atoms * 3, n_replicas * n_unit_atoms * 3))
        return expanded_third
