"""IBM quantum hardware routes: list the backends an account can reach.

The IBM credentials are held by the SERVER (an environment secret), never supplied
by a caller: a client must not be able to spend the owner's quantum credits, and
this server must not relay a stranger's token. Who may reach these routes at all is
decided upstream by the front door (Cloudflare Access for the owner, or a
time-boxed recruiter pass), so the token stays out of the browser entirely.

Which run reaches the QPU is per request: a solve carries its own ``hw`` block and
the front door's entitlement header. See tools/routes/solver.py.
"""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from nonogram.errors import ValidationError
from tools.errors import json_object, respond_error
from tools.state import set_busy

bp = Blueprint("hardware", __name__)

#: Upper bound on shots per hardware job — each shot costs real quantum credits.
MAX_SHOTS = 4096


def _ibm_token() -> str | None:
    """The IBM Quantum API token from the server environment, or None if unset.

    Deploy it as a secret (e.g. ``fly secrets set IBM_QUANTUM_TOKEN=…``). Unset ⇒ the
    hardware routes report 503 and the solver stays on the local simulator.
    """
    return os.environ.get("IBM_QUANTUM_TOKEN") or None


def _ibm_channel(data: dict) -> str:
    """The Runtime channel (not a secret): env override, else caller, else default.

    ``ibm_quantum_platform`` is the channel qiskit-ibm-runtime 0.30 and later expect.
    """
    return (
        os.environ.get("IBM_QUANTUM_CHANNEL") or data.get("channel") or "ibm_quantum_platform"
    )


@bp.route("/api/hw/backends", methods=["POST"])
def api_hw_backends():
    """List available IBM quantum backends, using the server-held credentials."""
    token = _ibm_token()
    if not token:
        return respond_error(
            "hardware_unconfigured", "IBM hardware is not configured on this server", 503
        )
    try:
        data = json_object(request.json or {})
    except ValidationError as exc:
        return respond_error("invalid_json", str(exc), 400)
    try:
        from nonogram.quantum import list_backends

        backends = list_backends(token, _ibm_channel(data))
        return jsonify(
            {"backends": [{"name": b[0], "qubits": b[1], "pending": b[2]} for b in backends]}
        )
    except Exception as exc:
        from tools.routes.solver import _sanitize_error

        # Runtime client errors can echo request internals or credentials —
        # sanitize before they reach a browser.
        return respond_error("hardware_error", _sanitize_error(exc), 400)


@bp.route("/api/hw/jobs", methods=["POST"])
def api_hw_submit():
    """Submit a Grover circuit to IBM and return its job id.

    Returns as soon as IBM has the job. The solver lock is held for the submission
    and released immediately: an IBM queue can run to minutes, and holding the one
    solver thread through it would 409 every other caller for the duration.
    """
    from tools.routes.solver import (
        _acquire_or_busy,
        _hw_or_error,
        _parse_validated_clues,
        _sanitize_error,
    )

    busy = _acquire_or_busy()
    if busy is not None:
        return busy
    try:
        row_clues, col_clues, rows, cols, err = _parse_validated_clues()
        if err is not None:
            return err
        data = json_object(request.json or {})
        hw_cfg, hw_err = _hw_or_error(data, rows, cols)
        if hw_err is not None:
            return hw_err
        if not hw_cfg:
            return respond_error(
                "hardware_not_allowed", "This run is not allowed to reach hardware", 403
            )
        from nonogram.quantum import submit_hardware_job

        submitted = submit_hardware_job(
            (row_clues, col_clues),
            token=hw_cfg["token"],
            backend_name=hw_cfg["backend_name"],
            channel=hw_cfg["channel"],
            shots=hw_cfg["shots"],
        )
        # creg_names stay here: collecting finds the register by scanning the result,
        # so a caller only ever needs the id.
        submitted.pop("creg_names", None)
        return jsonify({**submitted, "rows": rows, "cols": cols}), 202
    except Exception as exc:
        return respond_error("hardware_error", _sanitize_error(exc), 400)
    finally:
        set_busy(False)


@bp.route("/api/hw/jobs/<job_id>", methods=["GET"])
def api_hw_collect(job_id: str):
    """Report what became of a submitted job, and its counts once it is done.

    Takes no lock: polling a queue is not solving, and a visitor who reloaded
    mid-run has only the id left to ask with.
    """
    from tools.routes.solver import _sanitize_error

    token = _ibm_token()
    if not token:
        return respond_error(
            "hardware_unconfigured", "IBM hardware is not configured on this server", 503
        )
    try:
        from nonogram.quantum import collect_hardware_job

        return jsonify(collect_hardware_job(job_id, token, _ibm_channel({})))
    except Exception as exc:
        return respond_error("hardware_error", _sanitize_error(exc), 400)
