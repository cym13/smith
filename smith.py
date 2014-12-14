#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# TODO: keep track of the last IDs used to propose relative identification

"""
Smith: Super Mega Intuitive Todolist Helper

Usage: smith [options] [ID...]

Arguments:
    ID      A tasks ID
            ID supports special keywords:
                all         all tasks
                finished    all finished tasks
                virgins     all tasks with no progress at all
                recent      the five last updated tasks
                last        the last updated task

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


def show_tasks(todolist, IDs, *, compact=False, color=False, verbose=False):
    if not verbose:
        script_p      = ""
        script_args_p = ""
        comment_p     = ""

        if not compact:
            print_fmt = ("[{ID_col}{ID}{default}] "
                         "{title}\t{bar} "
                         "{progress}/{limit}")
        if compact:
            print_fmt = "{ID_col}{ID}{default}: {title} {progress}/{limit}"

    if verbose:
        if not compact:
            print_fmt = ( "[{ID_col}{ID}{default}] {title}\t{bar} "
                        + "{progress}/{limit}\n"
                        + "{script_p}{script}\n"
                        + "{script_args_p}{script_args}\n"
                        + "{comment_p}{comment}\n")

            script_p      = "Script: "
            script_args_p = "Args: "
            comment_p     = "Comment: "

        if compact:
            print_fmt = ("{ID_col}{ID}{default}: {title} {progress}/{limit}"
                         "{script_p}{script}"
                         "{script_args_p}{script_args}"
                         "{comment_p}{comment}")
            script_p      = " | "
            script_args_p = " | "
            comment_p     = " | "

    for ID in IDs:
        task = todolist[ID]

        print(re.sub("\n+", "\n", print_fmt.format(
                ID            = ID,
                ID_col        = COLOR["yellow"]  if color else "",
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


def bar(progress, limit, color=False, width=52):
    ratio  = progress/limit

    if color:
        if ratio <= 0.33:
            col = "red"
        elif ratio <= 0.66:
            col = "yellow"
        elif ratio < 1:
            col = "green"
        else:
            col = "magenta"
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
                    "# [%s] %s" % (ID, todolist[ID]["title"]),
                    "# This is a script for the SMITH todolist management tool",
                    "# It is called with the following arguments:",
                    "#      the current progress of the task",
                    "#      the limit set for the task",
                    "#      the argument field of the task",
                    ""]))

        subprocess.call([os.environ["EDITOR"], todolist[ID]["script"]])


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


def select_IDs(todolist, ID_request):
    if ID_request is None:
        return []

    # Function to append elements to a list only if not already in it
    append = lambda x,lst: x in lst or lst.append(x)

    IDs = []

    for ID in ID_request:
        # Ugly but needed to preserve explicit arguments priority
        if ID not in ("all", "recent", "last", "finished", "virgins"):
            append(ID, IDs)

            if ID not in todolist:
                print("No task with ID %s: ignoring" % ID, file=sys.stderr)

    if 'all' in ID_request:
        for i in todolist:
            append(i, IDs)

    if 'recent' in ID_request:
        lst = list(todolist.keys())
        lst.sort(key=lambda x: todolist[x]["mtime"])
        lst.reverse()
        for each in lst[:5]:
            append(each, IDs)

    if 'last' in ID_request:
        lst = list(todolist.keys())
        lst.sort(key=lambda x: todolist[x]["mtime"])
        lst.reverse()
        append(lst[0], IDs)

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
    args = docopt(__doc__, version=VERSION)

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

    # if called without option or argument (except --color)
    if not [ True for x in args if args[x] and x != "--color"]:
        args["--show"] = True
        args["ID"]     = ["recent"]

    IDs = select_IDs(todolist, args["ID"])

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
            p = os.popen(' '.join(todolist[ID]["script"],
                                  todolist[ID]["progress"],
                                  todolist[ID]["limit"],
                                  todolist[ID]["script_args"]))
            if p.close() is None:
                todolist[ID]["progress"] += 1

    if args["--export"]:
        json.dump({ x:todolist[x] for x in IDs }, sys.stdout)
        print()

    if args["--show"] or args["--compact"]:
        show_tasks(todolist, IDs,
                   compact=args["--compact"],
                   color=args["--color"],
                   verbose=args["--verbose"])

    json.dump(todolist, open(list_file, "w"))


if __name__ == "__main__":
    main()
