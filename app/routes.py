from flask import render_template, request, flash, send_from_directory, jsonify
import os
import multiprocessing
import python_distance

from . import application
from .config import COMPUTATIONS_DIR, RAW_PDB_DIR, QSCORE_THRESHOLD
from .computation import process_input, start_computation

pool = multiprocessing.Pool()

computation_results = {}


@application.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')

    try:
        comp_id, ids = process_input(request)
    except RuntimeError:
        flash('Cannot process file')
        return render_template('index.html')

    if not ids:
        flash('No chains detected')
        return render_template('index.html')

    filename = request.files['file'].filename
    return render_template('index.html', chains=ids, uploaded=True, comp_id=comp_id, filename=filename)


@application.route('/upload', methods=['POST'])
def upload():
    try:
        comp_id, ids = process_input(request)
    except RuntimeError:
        return jsonify({'status': 'failed', 'message': 'Cannot process file'}), 400

    if not ids:
        return jsonify({'status': 'failed', 'message': 'No protein chains detected'}), 400

    return jsonify({'status': 'ok', 'comp_id': comp_id, 'chains': ids}), 201


@application.route('/submit_calculation', methods=['POST'])
def submit_calculation():
    comp_id: str = request.form['comp-id']
    chain: str = request.form['chain']

    try:
        computation_results[comp_id] = start_computation(comp_id, chain, pool)
    except RuntimeError:
        return jsonify({'status': 'failed', 'message': 'Calculation start unsuccessful'}), 400

    return jsonify({'status': 'STARTED'}), 200


@application.route('/results', methods=['POST'])
def results():
    comp_id: str = request.form['comp-id']
    chain: str = request.form['chain']
    filename: str = request.form['filename']

    try:
        computation_results[comp_id] = start_computation(comp_id, chain, pool)
    except RuntimeError:
        flash('Calculation failed')
        return render_template('index.html')

    return render_template('results.html', query=chain, comp_id=comp_id, filename=filename)


@application.route('/details')
def get_details():
    comp_id: str = request.args.get('comp_id')
    chain: str = request.args.get('chain')
    obj: str = request.args.get('object')

    python_distance.prepare_aligned_PDBs(f'_{comp_id}:{chain}', obj, RAW_PDB_DIR,
                                         os.path.join(COMPUTATIONS_DIR, comp_id))

    return render_template('details.html', object=obj, query_chain=chain, comp_id=comp_id)


@application.route('/get_pdb')
def get_pdb():
    comp_id: str = request.args.get('comp_id')
    obj: str = request.args.get('object')

    if obj == '_query':
        file = 'query.pdb'
    else:
        file = f'{obj}.aligned.pdb'
    return send_from_directory(os.path.join(COMPUTATIONS_DIR, comp_id), file, cache_timeout=0)


@application.route('/get_results')
def get_results():
    comp_id: str = request.args.get('comp_id')

    total = len(computation_results[comp_id])
    completed = 0
    ret = []
    for chain_id, result in computation_results[comp_id].items():
        if result.ready():
            completed += 1
            status, qscore, rmsd, seq_id, aligned = result.get()
            if status == python_distance.Status.OK and qscore > QSCORE_THRESHOLD:
                ret.append({'object': chain_id,
                            'qscore': round(qscore, 3),
                            'rmsd': round(rmsd, 3),
                            'seq_id': round(seq_id, 3),
                            'aligned': aligned})

    final = sorted(ret, key=lambda x: x['qscore'], reverse=True)[:30]
    status = 'FINISHED' if completed == total else 'COMPUTING'

    return jsonify({'results': final,
                    'status': status,
                    'total': total,
                    'completed': completed}), 200
