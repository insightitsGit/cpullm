# Helios — Article

Verified prose constructed from source claims; unrecognized records remain attributed quotations. Missing sections are not stated in the selected evidence.

## Overview

Helios is a backup service.

Sources: rerun-manual-p0001

## Details

Helios stores encrypted backups and uses PostgreSQL for metadata.

Sources: rerun-manual-p0002, rerun-manual-p0003

It stores backup files in object storage and verifies backup checksums.

Sources: rerun-manual-p0004, rerun-manual-p0005

It retains backups for 30 days and runs backups every night.

Sources: rerun-manual-p0006, rerun-manual-p0007

It supports restoration by operators and records restoration events in an audit log.

Sources: rerun-manual-p0008, rerun-manual-p0009

It requires operator approval before deletion and reports backup failures to operators.

Sources: rerun-manual-p0010, rerun-manual-p0012

## Limitations

Helios doesn't support automatic regional failover.

Sources: rerun-manual-p0011
