# Helios — Report

Source quotations; design decisions are not inferred. Missing sections are not stated in the selected evidence.

## Overview

> Helios is a backup service.

Source: rerun-manual-p0001

> Helios stores encrypted backups.

Source: rerun-manual-p0002

> Helios uses PostgreSQL for metadata.

Source: rerun-manual-p0003

## Operations

> Helios stores backup files in object storage.

Source: rerun-manual-p0004

> Helios verifies backup checksums.

Source: rerun-manual-p0005

> Helios retains backups for 30 days.

Source: rerun-manual-p0006

> Helios runs backups every night.

Source: rerun-manual-p0007

> Helios supports restoration by operators.

Source: rerun-manual-p0008

> Helios records restoration events in an audit log.

Source: rerun-manual-p0009

> Helios requires operator approval before deletion.

Source: rerun-manual-p0010

> Helios reports backup failures to operators.

Source: rerun-manual-p0012

## Limitations

> Helios does not support automatic regional failover.

Source: rerun-manual-p0011
