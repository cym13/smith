#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Smith: Super Mega Intuitive Todolist Helper

Usage: smith [options] [ID...]

Arguments:
    ID      A tasks IDbe it a unique ID or a
            position number relative to the last command

            ID supports special keywords:
                all         all tasks
                last        the last updated task
                recent      the five last updated tasks
                finished    all finished tasks
                virgins     all tasks with no progress at all
                maxfirst    all tasks, most advanced first
                minfirst    all tasks, least advanced first

Options:
    -s, --show              Show tasks
    -t, --task              Create or edit a task
    -a, --action            Add or edit a task's action
    -r, --remove            Remove a task
    -d, --do                Do the action associated with a task
                            and update the progress accordingly
    -i, --import FILE       Read from a file the tasks to be added
                            If FILE is - then read from stdin
    -o, --export            Prints raw json task data to stdout
    -u, --update            Increments the task's progress by
    -U, --update-by N       Updates the task's progress by N
    -f, --file FILE         Use FILE to load and save the todolist
                            Default is ~/.config/smith/todolist
    -D, --script-dir DIR    Looks in DIR to find scripts
                            Default is ~/.config/smith/scripts/
    -c, --compact           Show tasks in a compact format
    -v, --verbose           Show more details about the tasks
    -G, --color             Print in color
    -h, --help              Print this help and exit
    -V, --version           Print the version number and exit

Smith relies on the EDITOR global variable to edit files
"""

VERSION=0.1

import os
import re
import sys
import json
import time
import math
import subprocess
from os import path
from docopt import docopt
from functools import reduce


# ANSI colors
COLOR = {"black":   "\033[30m",
         "red":     "\033[31m",
         "green":   "\033[32m",
         "yellow":  "\033[33m",
         "blue":    "\033[34m",
         "magenta": "\033[35m",
         "cyan":    "\033[36m",
         "white":   "\033[37m",
         "default": "\033[00m"}


def show_tasks(todolist, IDs, old_IDs, *,
               compact=False, color=False, verbose=False):
    if not verbose:
        script_p      = ""
        script_args_p = ""
        comment_p     = ""

        if not compact:
            print_fmt = ( "[{num_col}{num}{default}:{ID_col}{ID}{default}] "
                         "{title:<30}\t{bar} "
                         "{progress}/{limit}")
        if compact:
            print_fmt = ("{num_col}{num}{default}:{ID_col}{ID}{default} "
                         "{title} {progress}/{limit}")

    if verbose:
        if not compact:
            print_fmt = ( "[{num_col}{num}{default}:{ID_col}{ID}{default}] "
                          "{title:<30}\t{bar} "
                          "{progress}/{limit}\n"
                          "{script_p}{script}\n"
                          "{script_args_p}{script_args}\n"
                          "{comment_p}{comment}\n")

            script_p      = "Script:\t"
            script_args_p = "Args:\t"
            comment_p     = "Comment:\t"

        if compact:
            print_fmt = ("{num_col}{num}{default}:{ID_col}{ID}{default} "
                         "{title} {progress}/{limit}"
                         "{script_p}{script}"
                         "{script_args_p}{script_args}"
                         "{comment_p}{comment}")
            script_p      = " | "
            script_args_p = " | "
            comment_p     = " | "

    for num,ID in enumerate(IDs):
        task = todolist[ID]

        print(re.sub("\n+", "\n", print_fmt.format(
                ID            = ID,
                num           = num,
                ID_col        = COLOR["yellow"]  if color else "",
                num_col       = COLOR["green"]   if color else "",
                default       = COLOR["default"] if color else "",
                title         = task["title"],
                bar           = bar(task["progress"], task["limit"], color),
                progress      = task["progress"],
                limit         = task["limit"],
                script        = task["script"],
                script_args   = task["script_args"],
                comment       = task["comment"],
                script_p      = script_p      if task["script"]      else "",
                script_args_p = script_args_p if task["script_args"] else "",
                comment_p     = comment_p     if task["comment"]     else ""
            )))


def bar(progress, limit, color=False, width=30):
    ratio      = progress/limit

    if color:
        if ratio <= 0.33:
            col = "red"
        elif ratio <= 0.66:
            col = "yellow"
        elif ratio < 1:
            col = "green"
        else:
            col = "cyan"
    else:
        col = "default"

    return "[%s%s%s]" % (COLOR[col],
                         ("#" * math.floor(ratio * width)).ljust(width),
                         COLOR["default"]
                        )


def update_by(todolist, IDs, n):
    for ID in IDs:
        task = todolist[ID]
        task["progress"] += int(n)

        if task["progress"] > task["limit"]:
            task["progress"] = task["limit"]

        task["mtime"] = time.time()


def edit_task(todolist, IDs, scripts_dir):
    if not IDs:
        ID  = new_id()
        IDs = [ID]
        todolist[ID] = {
                "title":       "New task",
                "progress":    0,
                "limit":       1,
                "script":      "",
                "script_args": "",
                "comment":     "",
                "mtime":       0}

    for ID in IDs:
        task = todolist[ID]

        def set_att(att_name):
            return (input("%s [%s]:" % (att_name.capitalize(), task[att_name]))
                    or task[att_name])

        print("Editing [%s] %s:" % (ID, task["title"]))
        task["title"]       = set_att("title")
        task["progress"]    = int(set_att("progress"))
        task["limit"]       = int(set_att("limit"))
        task["script"]      = set_att("script")
        task["script_args"] = set_att("script_args")
        task["comment"]     = set_att("comment")
        task["mtime"]       = time.time()

        if task["script"] and '/' not in task["script"]:
            task["script"] = path.join(scripts_dir, task["script"])


def edit_action(todolist, IDs, scripts_dir):
    for ID in IDs:
        if not todolist[ID]["script"]:
            scriptname = input("Select a name for the script: ")
            if not scriptname:
                return
            if '/' not in scriptname:
                scriptname = path.join(scripts_dir, scriptname)

            todolist[ID]["script"] = scriptname

        if not path.exists(todolist[ID]["script"]):
            with open(todolist[ID]["script"], "w") as f:
                f.write('\n'.join([
                    "#!/bin/sh",
                    "#",
                    "# [%s] %s" % (ID, todolist[ID]["title"]),
                    "# This is a script for the SMITH todolist management tool",
                    "# It is called with the following arguments:",
                    "#      the current progress of the task",
                    "#      the limit set for the task",
                    "#      the argument field of the task",
                    ""]))

        subprocess.call([os.environ["EDITOR"], todolist[ID]["script"]])
        os.popen("chmod +x %s" % todolist[ID]["script"])


def new_id():
    # Yes, this is ugly. Deal with it.
    return hex(int(str(time.time()).replace('.', '')[:-4]))[2:].rjust(11, '0')

def import_data(todolist, input_file):
    if input_file == '-':
        ifile = sys.stdin
    else:
        ifile = open(path.expanduser(input_file))

    for ID,value in json.load(ifile):
        todolist[ID] = value

    if ifile is not sys.stdin:
        ifile.close()


def mkconfigdir(dir_path):
    todolist_path = path.join(dir_path, "todolist")
    scripts_path  = path.join(dir_path, "scripts/")

    if not path.exists(dir_path):
        os.mkdir(dir_path)

    if not path.exists(todolist_path):
        open(todolist_path, "w")

    if not open(todolist_path).read():
        json.dump(dict(), open(todolist_path, "w"))

    if not path.exists(scripts_path):
        os.mkdir(scripts_path)

def sorted_IDs(todolist, key):
    result = list(todolist.keys())
    result.sort(key=key)
    result.reverse()
    return result


def select_IDs(todolist, ID_request, old_IDs=[]):
    if ID_request is None:
        return []

    # Function to append elements to a list only if not already in it
    append = lambda x,lst: x in lst or lst.append(x)

    IDs = []
    sorted_by_mtime    = sorted_IDs(todolist, lambda x: todolist[x]["mtime"])
    sorted_by_progress = sorted_IDs(todolist,
                        lambda x: todolist[x]["progress"]/todolist[x]["limit"])

    if 'all' in ID_request:
        for i in sorted_by_mtime:
            append(i, IDs)
        ID_request.remove("all")

    if 'recent' in ID_request:
        for i in sorted_by_mtime[:5]:
            append(i, IDs)
        ID_request.remove("recent")

    if 'last' in ID_request:
        append(sorted_by_mtime[0], IDs)
        ID_request.remove("last")

    if 'finished' in ID_request:
        for i in sorted_by_progress:
            if todolist[i]["progress"] == todolist[i]["limit"]:
                append(i, IDs)
        ID_request.remove("finished")

    if 'virgins' in ID_request:
        for i in sorted_by_progress:
            if todolist[i]["progress"] == 0:
                append(i, IDs)
        ID_request.remove("virgins")

    if 'maxfirst' in ID_request:
        for i in sorted_by_progress:
            append(i, IDs)
        ID_request.remove("maxfirst")

    if 'minfirst' in ID_request:
        for i in sorted_by_progress[::-1]:
            append(i, IDs)
        ID_request.remove("minfirst")

    for ID in ID_request:
        if ID in todolist:
            append(ID, IDs)
        elif len(ID)<11 and ID.isnumeric() and int(ID)<len(old_IDs):
            append(old_IDs[int(ID)], IDs)
        else:
            print("No task with ID '%s': ignoring it" % ID, file=sys.stderr)

    return IDs


def main():
    args = docopt(__doc__, version=VERSION)

    tmp_ids_file = "/tmp/smith.tmp"
    smith_dir    = path.expanduser("~/.config/smith/")
    list_file    = args["--file"] or path.join(smith_dir, "todolist")
    if args["--script-dir"] is None:
        scripts_dir = path.join(smith_dir, "scripts")
    else:
        scripts_dir = path.expanduser(args["--script-dir"])

    if not args["--file"]:
        mkconfigdir(smith_dir)

    with open(list_file) as f:
        todolist = json.load(f)


    # if called without option or argument (except --color)
    if not [ True for x in args
                  if args[x]
                  and x not in ("--color", "ID")]:
        args["--show"] = True

    old_IDs = []
    if path.exists(tmp_ids_file):
        old_IDs = json.load(open(tmp_ids_file))

    IDs = select_IDs(todolist, args["ID"], old_IDs)


    if args["--import"]:
        import_data(todolist, args["--import"])

    if args["--update"]:
        update_by(todolist, IDs, 1)

    if args["--update-by"]:
        update_by(todolist, IDs, args["--update-by"])

    if args["--remove"]:
        for ID in IDs:
            todolist.pop(ID)
        IDs = []

    if args["--task"]:
        edit_task(todolist, IDs, scripts_dir)

    if args["--action"]:
        edit_action(todolist, IDs, scripts_dir)

    if args["--do"]:
        for ID in IDs:
            if not path.exists(todolist[ID]["script"]):
                print("No script for %s: ignoring" % ID, file=sys.stderr)
                continue
            task = todolist[ID].copy()
            update_by({ID: task}, [ID], 1)
            p = os.popen('%s %s %s %s ' % (task["script"],
                                           task["progress"],
                                           task["limit"],
                                           task["script_args"]))
            if p.close() is None:
                update_by(todolist, [ID], 1)

    if args["--export"]:
        json.dump({ x:todolist[x] for x in IDs }, sys.stdout)
        print()

    if args["--show"] or args["--compact"]:
        if not IDs:
            IDs = select_IDs(todolist, ["recent"])

        show_tasks(todolist, IDs, old_IDs,
                   compact=args["--compact"],
                   color=args["--color"],
                   verbose=args["--verbose"])

    json.dump(todolist, open(list_file, "w"))

    # keep track of the last IDs used to propose relative identification
    json.dump(IDs, open(tmp_ids_file, "w"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
