"""Detect variants with the Platypus Haplotype-Based variant caller.

http://www.well.ox.ac.uk/platypus
https://github.com/andyrimmer/Platypus
"""
import os

try:
    import pybedtools
except ImportError:
    pybedtools = None
import toolz as tz

from bcbio import bam, utils
from bcbio.distributed.transaction import file_transaction
from bcbio.pipeline import datadict as dd
from bcbio.pipeline import shared as pshared
from bcbio.provenance import do
from bcbio.variation import bamprep, bedutils, vcfutils

def run(align_bams, items, ref_file, assoc_files, region, out_file):
    """Run platypus variant calling, germline whole genome or exome.
    """
    assert out_file.endswith(".vcf.gz")
    if not utils.file_exists(out_file):
        p_out_file = out_file.replace(".vcf.gz", ".vcf")
        with file_transaction(p_out_file) as tx_out_file:
            for align_bam in align_bams:
                bam.index(align_bam, items[0]["config"])
            cmd = ["platypus", "callVariants", "--regions=%s" % _bed_to_platypusin(region, out_file, items),
                   "--bamFiles=%s" % ",".join(align_bams),
                   "--refFile=%s" % dd.get_ref_file(items[0]), "--output=%s" % tx_out_file,
                   "--logFileName", "/dev/null", "--verbosity=1"]
            cmd += ["--assemble=1"]
            cmd += ["--hapScoreThreshold", "10", "--scThreshold", "0.99", "--filteredReadsFrac", "0.9"]
            # Avoid filtering duplicates on high depth targeted regions where we don't mark duplicates
            if any(not tz.get_in(["config", "algorithm", "mark_duplicates"], data, True)
                   for data in items):
                cmd += ["--filterDuplicates=0"]
            do.run(cmd, "platypus variant calling")
        if p_out_file != out_file:
            post_process_cmd = "%s | vcfallelicprimitives | vcfstreamsort" % vcfutils.fix_ambiguous_cl()
            b_out_file = vcfutils.bgzip_and_index(p_out_file, items[0]["config"],
                                                  prep_cmd=post_process_cmd)
            assert b_out_file == out_file
    return out_file

def _bed_to_platypusin(region, base_file, items):
    """Convert BED file regions into Platypus custom inputs.
    """
    variant_regions = bedutils.merge_overlaps(tz.get_in(["config", "algorithm", "variant_regions"], items[0]),
                                              items[0])
    target = pshared.subset_variant_regions(variant_regions, region, base_file, items)
    if isinstance(target, basestring) and os.path.isfile(target):
        out_file = "%s-platypusregion.list" % utils.splitext_plus(base_file)[0]
        if not utils.file_exists(out_file):
            with file_transaction(out_file) as tx_out_file:
                with open(tx_out_file, "w") as out_handle:
                    for region in pybedtools.BedTool(target):
                        out_handle.write("%s:%s-%s\n" % (region.chrom, region.start, region.stop))
        return out_file
    else:
        return bamprep.region_to_gatk(target)
