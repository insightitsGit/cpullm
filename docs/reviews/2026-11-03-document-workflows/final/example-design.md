# Helios — Design

Source quotations; design decisions are not inferred. Missing sections are not stated in the selected evidence.

## Overview

> Helios is a backup service.

Source: helios-manual-p0001

## Requirements

> Helios requires operator approval before deletion.

Source: helios-manual-p0010

## Architecture

> Helios stores encrypted backups.

Source: helios-manual-p0002

> Helios uses PostgreSQL for metadata.

Source: helios-manual-p0003

> Helios stores backup files in object storage.

Source: helios-manual-p0004

## Interfaces

Not stated in the selected evidence.

## Operations

> Helios retains backups for 30 days.

Source: helios-manual-p0006

> Helios runs backups every night.

Source: helios-manual-p0007

> Helios supports restoration by operators.

Source: helios-manual-p0008

> Helios records restoration events in an audit log.

Source: helios-manual-p0009

> Helios reports backup failures to operators.

Source: helios-manual-p0012

## Limitations

> Helios does not support automatic regional failover.

Source: helios-manual-p0011

## Validation

> Helios verifies backup checksums.

Source: helios-manual-p0005
