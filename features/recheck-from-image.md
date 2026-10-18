# Feature: Re-check from image

Status: **not implemented** — do not wire into the app yet. Build when we need it.

## Problem

Intake reads (delivery note / scale photo) sometimes get fields wrong. The operator needs a way to run the vision extract again from the same image after a mistake, without re-uploading or losing the rest of the intake form.

## Goal

Add a **Re-check** action on an already-read photo (or note) that:

1. Calls the same intake read path again against that image.
2. Refreshes the extracted fields for that source.
3. Re-runs the scale-vs-handwrite / sum checks with the new values.
4. Leaves message fields and other photos untouched unless the operator applies changes.

## Out of scope for now

- No UI button, API route, or imports.
- No auto-retry loops.
- No overwrite of manually edited message fields without confirmation.

## When to build

Use this when operators report wrong marks, CTN, TW, PW, or scale kg often enough that "upload again" is too slow.
