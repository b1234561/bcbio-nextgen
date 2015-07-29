import os
import argparse
import os.path as op
import shutil
from collections import namedtuple

import pysam
from seqcluster import prepare_data as prepare
from seqcluster import make_clusters as main_cluster
from seqcluster.libs.inputs import parse_ma_file
from seqcluster.libs import parse

from bcbio.utils import file_exists, safe_makedir
from bcbio.provenance import do
from bcbio.distributed.transaction import tx_tmpdir, file_transaction
from bcbio.log import logger
from bcbio.pipeline import datadict as dd
from bcbio.pipeline.sample import process_alignment

MAX_EDIT_DISTANCE = 2

def run_prepare(data):
    out_dir = os.path.join(dd.get_work_dir(data[0]), "seqcluster", "prepare")
    out_dir = os.path.abspath(safe_makedir(out_dir))
    config_file = os.path.join(out_dir, "prepare.conf")
    prepare_dir = os.path.join(out_dir, "prepare")
    fn = []
    for sample in data:
        name = sample["rgnames"]['sample']
        fn.append("%s\t%s" % (sample['collapse'], name))
    args = namedtuple('args', 'debug print_debug minc minl maxl out')
    args = args(False, False, 1, 17, 40, out_dir)
    seq_l, sample_l = prepare._read_fastq_files(fn, args)
    ma_out = op.join(out_dir, "seqs.ma")
    seq_out = op.join(out_dir, "seqs.fastq")
    min_shared = max(int(len(fn) / 10.0), 1)
    if not file_exists(ma_out):
        with file_transaction(ma_out) as ma_tx:
            with open(ma_tx, 'w') as ma_handle:
                with open(seq_out, 'w') as seq_handle:
                    prepare._create_matrix_uniq_seq(sample_l, seq_l, ma_handle, seq_handle, min_shared)

    return [data]

def run_align(data):
    out_dir = os.path.join(dd.get_work_dir(data[0]), "seqcluster", "prepare")
    seq_out = op.join(out_dir, "seqs.fastq")
    data[0] = process_alignment(data[0], [seq_out, None])
    data = data[0][0]
    bam_file = dd.get_work_bam(data[0])
    bam_dir = os.path.join(dd.get_work_dir(data[0]), "align")
    new_bam_file = op.join(bam_dir, "seqs.bam")
    if not file_exists(new_bam_file):
        shutil.move(bam_file, new_bam_file)
        shutil.move(bam_file + ".bai", new_bam_file + ".bai")
        shutil.rmtree(op.join(bam_dir, data[0]["rgnames"]['sample']))
    data[0]['work_bam'] = new_bam_file
    return [data]

def run_cluster(data):
    out_dir = os.path.join(dd.get_work_dir(data[0]), "seqcluster", "cluster")
    out_dir = os.path.abspath(safe_makedir(out_dir))
    prepare_dir = op.join(dd.get_work_dir(data[0]), "seqcluster", "prepare")
    bam_file = op.join(dd.get_work_dir(data[0]), "align", "seqs.bam")
    cluster_dir = _cluster(bam_file, prepare_dir, out_dir, dd.get_ref_file(data[0]), dd.get_srna_gtf_file(data[0]))
    return data

def _cluster(bam_file, prepare_dir, out_dir, reference, annotation_file=None):
    if annotation_file:
        opts = "-g %s" % annotation_file
    ma_file = op.join(prepare_dir, "seqs.ma")
    cl = ["cluster", "-o", out_dir, "-m", ma_file, "-a", bam_file, "-r", reference]
    p = argparse.ArgumentParser()
    sbp = p.add_subparsers()
    parse.add_subparser_cluster(sbp)
    args = p.parse_args(cl)
    if not file_exists(op.join(out_dir, "counts.tsv")):
        main_cluster.cluster(args)
    return out_dir

def _update(data,  prepare_dir, bam_file, cluster_dir):
    for s in data:
        s["seqs_ma"] = os.path.join(prepare_dir, "seqs.ma")
        s["seqs_bam"] = bam_file
        s["clusters"] = os.path.join(cluster_dir, "counts.tsv")
    return data

def qc(data, args):
    """fastqc for the sam file"""
    sam_file = data['align']
    out_dir = os.path.basename(sam_file) + "_fastq"
    cmd = "fastqc {sam_file} -f sam -o {out_dir}".format(**locals())
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
        do.run(cmd)
    else:
        logger.info("%s has already been QC, skipping." % (sam_file))
    return data

