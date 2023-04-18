import pytest
from qiskit import QuantumCircuit, QuantumRegister
from nonogram import apply_diffusion

@pytest.fixture
def n_qubits():
    return 3

@pytest.fixture
def q():
    return QuantumRegister(n_qubits(), 'q')

@pytest.fixture
def c(q):
    return QuantumCircuit(q)

def test_apply_diffusion(c, q, n_qubits):
    apply_diffusion(c,q)
    assert len(c) == 10*n_qubits-4
    expected_gates = ['h','x','h','mcx','h','x','h','q','h','x','h','mcx','h','x','h','q','h','x','h','mcx','h','x','h','q','h','x','h','mcx','h','x','h','q']
    for i, gates in enumerate(expected_gates):
        assert c.data[i][0].name == gate
    assert c.num_qubits == n_qubits