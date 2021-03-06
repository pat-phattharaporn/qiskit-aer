# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# pylint: disable=invalid-name
"""
Qiskit Aer Unitary Simulator Backend.
"""

import logging
from qiskit.util import local_hardware_info
from qiskit.providers.models import QasmBackendConfiguration

from ..aererror import AerError
from ..version import __version__
from .aerbackend import AerBackend
from .backend_utils import (cpp_execute, available_methods,
                            MAX_QUBITS_STATEVECTOR)
# pylint: disable=import-error, no-name-in-module
from .controller_wrappers import unitary_controller_execute

# Logger
logger = logging.getLogger(__name__)


class UnitarySimulator(AerBackend):
    """Ideal quantum circuit unitary simulator.

    **Configurable Options**

    The `UnitarySimulator` supports CPU and GPU simulation methods and
    additional configurable options. These may be set using the appropriate kwargs
    during initialization. They can also be set of updated using the
    :meth:`set_options` method.

    Run-time options may also be specified as kwargs using the :meth:`run` method.
    These will not be stored in the backend and will only apply to that execution.
    They will also override any previously set options.

    For example, to configure a a single-precision simulator

    .. code-block:: python

        backend = UnitarySimulator(precision='single')

    **Backend Options**

    The following configurable backend options are supported

    * ``method`` (str): Set the simulation method supported methods are
      ``"unitary"`` for CPU simulation, and ``"untiary_gpu"``
      for GPU simulation (Default: ``"unitary"``).

    * ``precision`` (str): Set the floating point precision for
      certain simulation methods to either ``"single"`` or ``"double"``
      precision (default: ``"double"``).

    * ``"initial_unitary"`` (matrix_like): Sets a custom initial unitary
      matrix for the simulation instead of identity (Default: None).

    * ``"validation_threshold"`` (double): Sets the threshold for checking
      if initial unitary and target unitary are unitary matrices.
      (Default: 1e-8).

    * ``"zero_threshold"`` (double): Sets the threshold for truncating
      small values to zero in the result data (Default: 1e-10).

    * ``"max_parallel_threads"`` (int): Sets the maximum number of CPU
      cores used by OpenMP for parallelization. If set to 0 the
      maximum will be set to the number of CPU cores (Default: 0).

    * ``"max_parallel_experiments"`` (int): Sets the maximum number of
      qobj experiments that may be executed in parallel up to the
      max_parallel_threads value. If set to 1 parallel circuit
      execution will be disabled. If set to 0 the maximum will be
      automatically set to max_parallel_threads (Default: 1).

    * ``"max_memory_mb"`` (int): Sets the maximum size of memory
      to store a state vector. If a state vector needs more, an error
      is thrown. In general, a state vector of n-qubits uses 2^n complex
      values (16 Bytes). If set to 0, the maximum will be automatically
      set to half the system memory size (Default: 0).

    * ``"statevector_parallel_threshold"`` (int): Sets the threshold that
      2 * "n_qubits" must be greater than to enable OpenMP
      parallelization for matrix multiplication during execution of
      an experiment. If parallel circuit or shot execution is enabled
      this will only use unallocated CPU cores up to
      max_parallel_threads. Note that setting this too low can reduce
      performance (Default: 14).
    """

    _DEFAULT_CONFIGURATION = {
        'backend_name': 'unitary_simulator',
        'backend_version': __version__,
        'n_qubits': MAX_QUBITS_STATEVECTOR // 2,
        'url': 'https://github.com/Qiskit/qiskit-aer',
        'simulator': True,
        'local': True,
        'conditional': False,
        'open_pulse': False,
        'memory': False,
        'max_shots': int(1e6),  # Note that this backend will only ever
                                # perform a single shot. This value is just
                                # so that the default shot value for execute
                                # will not raise an error when trying to run
                                # a simulation
        'description': 'A C++ unitary simulator for QASM Qobj files',
        'coupling_map': None,
        'basis_gates': [
            'u1', 'u2', 'u3', 'u', 'p', 'r', 'rx', 'ry', 'rz', 'id', 'x',
            'y', 'z', 'h', 's', 'sdg', 'sx', 't', 'tdg', 'swap', 'cx',
            'cy', 'cz', 'csx', 'cp', 'cu1', 'cu2', 'cu3', 'rxx', 'ryy',
            'rzz', 'rzx', 'ccx', 'cswap', 'mcx', 'mcy', 'mcz', 'mcsx',
            'mcp', 'mcu1', 'mcu2', 'mcu3', 'mcrx', 'mcry', 'mcrz',
            'mcr', 'mcswap', 'unitary', 'diagonal', 'multiplexer', 'delay'
        ],
        'gates': []
    }

    _AVAILABLE_METHODS = None

    def __init__(self,
                 configuration=None,
                 properties=None,
                 provider=None,
                 **backend_options):

        self._controller = unitary_controller_execute()

        if UnitarySimulator._AVAILABLE_METHODS is None:
            UnitarySimulator._AVAILABLE_METHODS = available_methods(
                self._controller,
                ['automatic', 'unitary', 'unitary_gpu', 'unitary_thrust'])

        if configuration is None:
            configuration = QasmBackendConfiguration.from_dict(
                UnitarySimulator._DEFAULT_CONFIGURATION)

        super().__init__(configuration,
                         properties=properties,
                         available_methods=UnitarySimulator._AVAILABLE_METHODS,
                         provider=provider,
                         backend_options=backend_options)

    def _execute(self, qobj):
        """Execute a qobj on the backend.

        Args:
            qobj (QasmQobj): simulator input.

        Returns:
            dict: return a dictionary of results.
        """
        return cpp_execute(self._controller, qobj)

    def _validate(self, qobj):
        """Semantic validations of the qobj which cannot be done via schemas.
        Some of these may later move to backend schemas.
        1. Set shots=1
        2. No measurements or reset
        3. Check number of qubits will fit in local memory.
        """
        name = self.name()
        if getattr(qobj.config, 'noise_model', None) is not None:
            raise AerError("{} does not support noise.".format(name))

        n_qubits = qobj.config.n_qubits
        max_qubits = self.configuration().n_qubits
        if n_qubits > max_qubits:
            raise AerError(
                'Number of qubits ({}) is greater than max ({}) for "{}" with {} GB system memory.'
                .format(n_qubits, max_qubits, name,
                        int(local_hardware_info()['memory'])))
        if qobj.config.shots != 1:
            logger.info('"%s" only supports 1 shot. Setting shots=1.', name)
            qobj.config.shots = 1
        for experiment in qobj.experiments:
            exp_name = experiment.header.name
            if getattr(experiment.config, 'shots', 1) != 1:
                logger.info(
                    '"%s" only supports 1 shot. '
                    'Setting shots=1 for circuit "%s".', name, exp_name)
                experiment.config.shots = 1
            for operation in experiment.instructions:
                if operation.name in ['measure', 'reset']:
                    raise AerError(
                        'Unsupported {} instruction {} in circuit {}'.format(
                            name, operation.name, exp_name))
