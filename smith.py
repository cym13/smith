#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smith: Surely the Most Intriguing Todolist Helper

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
                byprogress  all tasks, most advanced first
                bydate      all tasks, by date of creation (more recent first)

Options:
    -s, --show              Show tasks
    -t, --task              Create or edit a task
    -a, --action            Add or edit a task's action
    -r, --remove            Remove a task
    -d, --do                Do the action associated with a task
                            and update the progress accordingly
    -i, --import FILE       Read from a file or a url the tasks to be added
                            If FILE is - then read from stdin
    -o, --export            Prints raw json task data to stdout
    -u, --update            Increments the task's progress by
    -U, --update-by N       Updates the task's progress by N
    -f, --file FILE         Use FILE to load and save the todolist
                            Default is ~/.config/smith/todolist
    -D, --script-dir DIR    Looks in DIR to find scripts
                            Default is ~/.config/smith/scripts/
    -c, --compact           Show tasks in a compact format
    -v, --verbose           Show more details about tasks
    -R, --reverse           Reverse the order of the selected tasks
    -T, --new-title TITLE   Change the tasks title to TITLE
    -h, --help              Print this help and exit
    -V, --version           Print the version number and exit

Smith relies on the EDITOR global variable to edit files
"""

VERSION="1.2.0"

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
COLOR = {"black"   : "\033[30m",
         "red"     : "\033[31m",
         "green"   : "\033[32m",
         "yellow"  : "\033[33m",
         "blue"    : "\033[34m",
         "magenta" : "\033[35m",
         "cyan"    : "\033[36m",
         "white"   : "\033[37m",
         "default" : "\033[00m"}


def show_tasks(todolist, IDs, old_IDs, *,
               compact=False, verbose=False, color=False):
    """
    Display tasks from `todolist' with id in `IDs' or `old_IDs' in case of
    temporary reference.

    Writes on stdout
    Returns nothing
    """

    if not compact:
        print_fmt = ( "[{num_col}{num}{default}:{ID_col}{ID}{default}] "
                     "{dl_col}{title:<30}{default}\t{bar} "
                     "{progress}/{limit}")

    elif compact:
            print_fmt = ("{num_col}{num}{default}:{ID_col}{ID}{default} "
                         "{dl_col}{title}{default} {progress}/{limit}")

    if not verbose:
        deadline_p    = ""
        script_p      = ""
        script_args_p = ""
        comment_p     = ""

    elif verbose:
        if not compact:
            print_fmt +=  ("\n"
                           "{deadline_p}{deadline}\n"
                           "{script_p}{script}\n"
                           "{script_args_p}{script_args}\n"
                           "{comment_p}{comment}\n")

            deadline_p    = COLOR["magenta"]+ "Deadline"+ COLOR["default"]+":\t"
            script_p      = COLOR["magenta"]+ "Script"  + COLOR["default"]+":\t"
            script_args_p = COLOR["magenta"]+ "Args"    + COLOR["default"]+":\t"
            comment_p     = COLOR["magenta"]+ "Comment" + COLOR["default"]+": "

        elif compact:
            print_fmt += ("{script_p}{script}"
                          "{script_args_p}{script_args}"
                          "{comment_p}{comment}")

            deadline_p    = " | "
            script_p      = " | "
            script_args_p = " | "
            comment_p     = " | "

    for num,ID in enumerate(IDs):
        task     = todolist[ID]
        deadline = task["deadline"]

        if deadline == "":
            dl_col = ""

        elif time.time() < task["deadline_limits"][0]:
            dl_col = COLOR["default"]

        elif (task["deadline_limits"][0] < time.time()
                                         < task["deadline_limits"][1]):
            dl_col = COLOR["magenta"]

        elif time.time() >= task["deadline_limits"][1]:
            dl_col = COLOR["red"]

        print(re.sub("\n+", "\n", print_fmt.format(
                ID            = ID,
                num           = num,
                ID_col        = COLOR["yellow"]  if color else "",
                num_col       = COLOR["green"]   if color else "",
                default       = COLOR["default"] if color else "",
                dl_col        = dl_col,
                title         = task["title"],
                bar           = bar(task["progress"], task["limit"], color),
                progress      = task["progress"],
                limit         = task["limit"],
                script        = task["script"],
                script_args   = task["script_args"],
                comment       = task["comment"],
                deadline      = task["deadline"],
                deadline_p    = deadline_p    if task["deadline"]    else "",
                script_p      = script_p      if task["script"]      else "",
                script_args_p = script_args_p if task["script_args"] else "",
                comment_p     = comment_p     if task["comment"]     else "",
            )))


def bar(progress, limit, color=False, width=30):
    """
    Returns an ascii bar showing the progress/limit ratio with width `width'
    """
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
        col = None

    return "[%s%s%s]" % (COLOR[col] if color else "",
                         ("#" * math.floor(ratio * width)).ljust(width),
                         COLOR["default"] if color else "")


def update_by(todolist, IDs, n):
    """
    Updates the progress of tasks from `todolist' with ids `IDs' by `n'
    Returns nothing
    """
    for ID in IDs:
        task = todolist[ID]
        task["progress"] += int(n)

        if task["progress"] > task["limit"]:
            task["progress"] = task["limit"]

        task["mtime"]     = time.time()


def edit_task(todolist, IDs, scripts_dir, color):
    """
    Edit tasks from `todolist' with ids in `IDs'
    `script_dir' is directory where the scripts are stored

    If IDs is void, a new task is created.

    Returns nothing
    """
    if not IDs:
        ID  = new_id()
        IDs = [ID]
        todolist[ID] = {
                "title"           : "New task",
                "progress"        : 0,
                "limit"           : 1,
                "script"          : "",
                "script_args"     : "",
                "comment"         : "",
                "deadline"        : "",
                "deadline_limits" : [],
                "mtime"           : 0}

    def set_att(att_name):
        prompt = "{f_col}{f_name} {default_col}[{f_default}]: ".format(
                        f_col       = COLOR["magenta"] if color else "",
                        default_col = COLOR["default"] if color else "",
                        f_name      = att_name.capitalize(),
                        f_default   = task[att_name])
        return input(prompt) or task[att_name]

    for ID in IDs:
        task = todolist[ID]

        print("Editing [{col_ID}{ID}{def_col}] {title}:".format(
                        col_ID  = COLOR["yellow"]  if color else "",
                        def_col = COLOR["default"] if color else "",
                        ID      = ID,
                        title   = task["title"]))

        task["title"]       = set_att("title")
        task["progress"]    = int(set_att("progress"))
        task["limit"]       = int(set_att("limit"))
        task["script"]      = set_att("script")
        task["script_args"] = set_att("script_args")
        task["comment"]     = set_att("comment")
        print("Deadline format: DD[[/MM]/YYYY]")
        task["deadline"]    = set_att("deadline")
        task["mtime"]       = time.time()

        if task["progress"] < 0:
            task["progress"] = 0

        if task["limit"] < 0:
            task["limit"] = 1

        if task["script"] and '/' not in task["script"]:
            task["script"] = path.join(scripts_dir, task["script"])

        if task["deadline"]:
            if task["deadline"].count("/") < 1:
                task["deadline"] += "/" + str(time.localtime().tm_mon)
            if task["deadline"].count("/") < 2:
                task["deadline"] += "/" + str(time.localtime().tm_year)

            try:
                deadline = time.mktime(time.strptime(task["deadline"],
                                                     "%d/%m/%Y"))
            except ValueError:
                print("Bad date format: ignoring")
                task["deadline"] = None
                task["deadline_limits"] = []
                continue

            limit_unit = (deadline - time.time()) / 4
            task["deadline_limits"] = [time.time() + limit_unit * 2,
                                       time.time() + limit_unit * 3]


def edit_action(todolist, IDs, scripts_dir):
    """
    For each task in `todolist' with ids `IDs' edits the associated script.
    The default scripts are stored in `scripts_dir'.

    If no script is set, a new one is created.

    Edition is done using the EDITOR defined in the environnement variable.

    Returns nothing.
    """
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


def do_action(todolist, IDs):
    """
    Launches the script of each task in `todolist' with ids in `IDs'
    passing the progress, the limit and user-defined variable as arguments.

    If the script returns 0, the progress is updated.

    Returns nothing.
    """
    for ID in IDs:
        todolist[ID]["mtime"] = time.time()

        if not path.exists(todolist[ID]["script"]):
            print("No script for %s: ignoring" % ID, file=sys.stderr)
            continue

        elif todolist[ID]["progress"] == todolist[ID]["limit"]:
            print("Task already finished %s: ignoring" % ID, file=sys.stderr)
            continue

        task = todolist[ID].copy()
        update_by({ID: task}, [ID], 1)
        try:
            p = subprocess.call([task["script"],
                             str(task["progress"]),
                             str(task["limit"]),
                                 task["script_args"]])
        except ProcessLookupError:
            p = -1

        if p == 0:
            update_by(todolist, [ID], 1)


def new_id():
    """
    Returns a new task id based on current time's timestamp.
    """
    # Yes, this is ugly. Deal with it.
    return hex(int(str(time.time()).replace('.', '')[:-4]))[2:].rjust(11, '0')


def import_data(todolist, input_file):
    """
    Imports json datas from `input_file' into `todolist'.
    If the input_file is '-', reads from stdin.
    if the input_file is a url, transparently import data from it.

    Return nothing.
    """
    if input_file == '-':
        data = sys.stdin.read()
    elif '://' in input_file and not path.exists(input_file):
        from urllib import request, error
        try:
            ifile = request.urlopen(input_file).read().decode("utf8")
        except error.URLError as e:
            print("Unable to open url %s: ignoring"%input_file, file=sys.stderr)
            return
    else:
        try:
            data = open(path.expanduser(input_file)).read()
        except:
            print("Unable to open %s: ignoring" % input_file, file=sys.stderr)
            return

    for ID,value in json.loads(data).items():
        todolist[ID] = value


def mkconfigdir(dir_path):
    """
    Makes the default configuration directories and files in `dir_path'
    Returns nothing.
    """
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
    """
    Returns the `todolist' ids sorted using `key' from max to min
    """
    result = list(todolist.keys())
    result.sort(key=key)
    result.reverse()
    return result


def select_IDs(todolist, ID_request, old_IDs=[]):
    """
    Returns the list of tasks from `todolist' matched by `ID_request'

    `old_IDs' shall contain the list of IDs from a previous command
    for temporary indexes.
    """
    if ID_request is None:
        return []

    # Function to append elements to a list only if not already in it
    append = lambda x,lst: x in lst or lst.append(x)

    IDs = []
    sorted_by_date     = sorted_IDs(todolist, lambda x: int(x, 16))
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

    if 'byprogress' in ID_request:
        for i in sorted_by_progress:
            append(i, IDs)
        ID_request.remove("byprogress")

    if 'bydate' in ID_request:
        for i in sorted_by_date:
            append(i, IDs)
        ID_request.remove("bydate")

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


    # if called without option or argument
    if not [ True for x in args
                  if args[x]
                  and x not in ("ID") ]:
        args["--show"] = True

    old_IDs = []
    if path.exists(tmp_ids_file):
        old_IDs = json.load(open(tmp_ids_file))

    if not args["ID"] and args["--remove"]:
        return # Never use default arguments with --remove

    if not args["ID"] and (args["--show"] or args["--compact"]):
        args["ID"] = ["recent"]

    IDs = select_IDs(todolist, args["ID"], old_IDs)

    # Only color if stdout is not redirected
    color = os.isatty(sys.stdout.fileno()),


    if args["--reverse"]:
        IDs.reverse()

    if args["--import"]:
        import_data(todolist, args["--import"])

    if args["--update"]:
        update_by(todolist, IDs, 1)

    if args["--update-by"]:
        try:
            update_by(todolist, IDs, args["--update-by"])
        except ValueError as e:
            sys.exit(e)

    if args["--remove"]:
        for ID in IDs:
            todolist.pop(ID)
        IDs = []

    if args["--task"]:
        edit_task(todolist, IDs, scripts_dir, color)

    if args["--action"]:
        edit_action(todolist, IDs, scripts_dir)

    if args["--new-title"]:
        for ID in IDs:
            todolist[ID]["title"] = args["--new-title"]

    if args["--do"]:
        do_action(todolist, IDs)

    if args["--export"]:
        json.dump({ x:todolist[x] for x in IDs }, sys.stdout)
        print()

    if args["--show"] or args["--compact"]:
        show_tasks(todolist, IDs, old_IDs,
                   compact=args["--compact"],
                   verbose=args["--verbose"],
                   color=color)

        # keep track of the last IDs used to propose relative identification
        json.dump(IDs, open(tmp_ids_file, "w"))

    json.dump(todolist, open(list_file, "w"))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        pass
