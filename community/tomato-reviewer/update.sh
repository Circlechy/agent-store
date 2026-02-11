#!/usr/bin/env bash
scripts/update_files.py
rm -rf build
rm -rf tomato_review.egg-info
pip install .
