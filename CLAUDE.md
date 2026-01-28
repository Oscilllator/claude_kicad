# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/claude-code) when working with this repository.

## Project Overview

This project is a repository of skills that claude can use to interact with kicad projects.

## Build & Development Commands

<!-- Add common commands here, e.g.: -->
<!-- - `npm install` - Install dependencies -->
<!-- - `npm run build` - Build the project -->
<!-- - `npm test` - Run tests -->

## Code Style Guidelines

<!-- Add any project-specific conventions -->

## Architecture Notes

Skills are located in the `skills/` directory. Each skill has:
- A Python script that performs the task
- A markdown file describing usage

## Available Skills

### kicad-component-props
Extracts properties of a component by reference designator from a KiCad project.

```bash
python3 skills/kicad_component_props.py --project <project_dir> --ref <reference>
```

See `skills/kicad-component-props.md` for full documentation.

## Useful paths:

example kicad projects:
/home/harry/kicad

pre-existing kicad bom checking tool:
/home/harry/bom_checker

kicad jlcpcb extension:
Location: `/home/harry/.local/share/kicad/7.0/scripting/plugins/kicad-jlcpcb-tools`

Tool to pull down the data of a component from lcsc for use in kicad:
easyeda2kicad --full  --output ~/kicad/user-kicad-library/easyeda2kicad --lcsc_id C2297 --overwrite
