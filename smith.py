#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smith: Super Mega Intuitive Todolist Helper

Usage: smith [options] [ID...]

Arguments:
    ID      A tasks ID
            ID supports special keywords:
                all         all tasks
                finished    all finished tasks
                recent      the five last updated tasks
                virgins     all tasks with no progress at all

Options:
    -s, --show              Show tasks
    -S, --show-short        Show tasks in a compact format
    -t, --task              Create or edit a task
    -a, --action            Add or edit a task's action
    -r, --remove            Remove a task
    -d, --do                Do the action associated with a task
                            and update the progress accordingly
    -i, --import FILE       Read from a file the tasks to be added
                            If FILE is - then read from stdin
    -o, --export            Prints raw json task data to stdout
    -u, --update-by N       Updates the task's progress by N
    -f, --file FILE         Use FILE to load and save the todolist
                            Default is ~/.config/smith/todolist
    -D, --script-dir DIR    Looks in DIR to find scripts
                            Default is ~/.config/smith/scripts/
    -h, --help              Print this help and exit
    -V, --version           Print the version number and exit

Smith relies on the EDITOR global variable to edit files
"""

import os
import sys
import json
import subprocess
from os import path
from docopt import docopt


def import_data(path):
    ...


def show_tasks(todolist, IDs, *, compact=False):
    ...


def edit_task(todolist, IDs, scripts_dir):
    ...


def edit_script(todolist, IDs, scripts_dir):
    for ID in IDs:
        if not todolist[ID]["script"]:
            scriptname = input("Select a name for the script: ")
            if '/' not in scriptname:
                scriptname = path.join(smith_dir, scriptname)

            todolist[ID]["script"] = scriptname

        if not path.exists(todolist[ID]["script"]):
            with open(todolist[ID]["script"], "w") as f:
                f.write('\n'.join([
                    "# [%s] %s" % (ID, todolist[ID]["title"]),
                    "# This is a script for the SMITH todolist management tool",
                    "# It is called with the following arguments:",
                    "#      the current progress of the task",
                    "#      the limit set for the task",
                    "#      the argument field of the task",
                    ""]))

        subprocess.Popen([os.environ["EDITOR"], todolist[ID]["script"]])


def convert_id_timestamp(ID):
    if typeof(ID) is int:
        return 't' + hex(timestamp)[2:]

    if ID.startswith('t'):
        return int(ID[1:], 16)


def mkconfigdir(dir_path):
    todolist_path = path.join(dir_path, "todolist")
    scripts_path  = path.join(dir_path, "scripts/")

    if not path.exists(dir_path):
        os.mkdir(dir_path)

    if not path.exists(todolist_path):
        open(todolist_path, "w")

    json.dump("{}", open(todolist_path, "w"))

    if not path.exists(scripts_path):
        os.mkdir(scripts_path)


def select_IDs(todolist, ID_request):
    if ID_request is None:
        return []

    # Function to append elements to a list only if not already in it
    append = lambda x,lst: x in lst or lst.append(x)

    IDs = []

    for ID in ID_request:
        if todolist[ID]:
            append(ID, IDs)
        elif ID not in ("all", "recent", "finished", "virgins"):
            print("No task with ID %s: ignoring" % ID, file=sys.stderr)

    if 'all' in ID_request:
        for i in todolist.keys():
            append(i, IDs)

    if 'recent' in ID_request:
        lst = todolist.keys()
        lst.sort()
        for each in lst[:5]:
            append(i, IDs)

    if 'finished' in ID_request:
        for i in todolist.keys():
            if todolist[i]["progress"] == todolist[i]["limit"]:
                append(i, IDs)

    if 'virgins' in ID_request:
        for i in todolist.keys():
            if todolist[i]["progress"] == 0:
                append(i, IDs)

    return IDs



def main():
    args = docopt(__doc__)

    smith_dir   =  path.expanduser("~/.config/smith/")
    list_file   =  args["--file"] or path.join(smith_dir, "todolist")
    if args["--script-dir"] is None:
        scripts_dir = path.join(smith_dir, "scripts")
    else:
        scripts_dir = path.expanduser(args["--script-dir"])

    if not args["--file"]:
        mkconfigdir(smith_dir)

    with open(list_file) as f:
        todolist = json.load(f)

    IDs = select_IDs(todolist, args["ID"])

    if args["--import"]:
        for ID,value in import_data(args["--import"]):
            todolist[ID] = value

    if args["--update-by"]:
        for ID in IDs:
            todolist[ID]["progress"] += args["--update-by"]

    if args["--remove"]:
        for ID in IDs:
            todolist.remove(ID)

    if args["--task"]:
        edit_task(todolist, IDs, scripts_dir)

    if args["--action"]:
        edit_action(todolist, IDs, scripts_dir)

    if args["--do"]:
        for ID in IDs:
            p = os.popen(' '.join(todolist[ID]["script"],
                                  todolist[ID]["progress"],
                                  todolist[ID]["limit"]))
            if p.close() is None:
                todolist[ID]["progress"] += 1

    if args["--export"]:
        json.dump({ x:todolist[x] for x in IDs }, sys.stdout)
        print()

    if args["--show"] or args["--show-short"]:
        show_tasks(todolist, IDs, compact=arg["--show-short"])


if __name__ == "__main__":
    main()
