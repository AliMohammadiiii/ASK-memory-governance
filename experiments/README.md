# Experiment records

This directory contains run definitions, authorization records, and indexes for
registered experiments. It does not contain private labels, provider keys, or
large generated runs.

An experiment record should identify its dataset contract, configuration,
prompt hashes, model identifiers, execution status, output location, and claim
eligibility. Prospective records do not count as observed results. Names that
include protocol terms such as `FINAL` or `FROZEN` describe the recorded study
state; they do not create a filesystem lock or prevent repository maintenance.
