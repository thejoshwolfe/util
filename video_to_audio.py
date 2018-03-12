#!/usr/bin/env python3

__doc__ = """
uses ffmpeg to extract the audio from video files.

outputs audio in the .mka container format.
no lossy transformation is performed on the audio itself.
"""

import sys
import os
import subprocess
import itertools

import multiprocessing
cpu_count = multiprocessing.cpu_count()

def cli():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="+", help="dir or file that is the root of this operation")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-i", "--in-place", action="store_true", default=False, help="delete inputs after conversion")
    parser.add_argument("--just-print", action="store_true", default=False)
    parser.add_argument("--ignore-unrecognized", action="store_true", default=False)
    parser.add_argument("--skip-sanity-check", action="store_true", default=False)
    parser.add_argument("--output")
    parser.add_argument("-j", "--jobs", type=int, default=cpu_count, help="default: {}. use 0 for unlimited".format(cpu_count))

    args = parser.parse_args()
    main(args.root, args)

def get_files_in(root):
    try: items = os.listdir(root)
    except NotADirectoryError:
        yield root
        return
    for item in items:
        yield from get_files_in(os.path.join(root, item))

class Job:
    def __init__(self, input_path, single_file_mode, options, parallel_count):
        file_extension = ".mka"
        if options.output != None:
            if options.output.endswith(os.path.sep):
                single_file_mode = False
            if single_file_mode:
                output_path = options.output
            else:
                output_path = os.path.join(options.output, os.path.split(input_path + file_extension)[1])
        else:
            # right next to it
            output_path = input_path + file_extension

        self.input_path = input_path
        self.output_path = output_path
        self.report_start = parallel_count == 1
        self.verbose = options.verbose
        self.just_print = options.just_print
        self.in_place = options.in_place
        self.skip_sanity_check = options.skip_sanity_check
        self.process = None
        self.done = False

    def start(self, numerator, denominator):
        if self.report_start and self.verbose >= 1:
            print("[{}/{}] converting: {}".format(numerator, denominator, self.input_path))
        if self.verbose >= 2:
            cmd = ["ffmpeg", "-i", self.input_path, "-vn", "-acodec", "copy", self.output_path]
        else:
            cmd = ["ffmpeg", "-loglevel", "fatal", "-i", self.input_path, "-vn", "-acodec", "copy", self.output_path]

        if self.just_print:
            print(" ".join(cmd))
        else:
            self.process = subprocess.Popen(cmd)

    def handle_maybe_done(self, numerator, denominator):
        if self.done: raise ASDF
        if self.just_print:
            self.done = True
        else:
            if self.process.poll() != None:
                self.done = True
                if not self.skip_sanity_check:
                    # sanity check
                    input_size = os.stat(self.input_path).st_size
                    output_size = os.stat(self.output_path).st_size
                    if input_size > 1000000:
                        # we shouldn't get any smaller than 10%, right?
                        if output_size < 100000:
                            raise Exception("something looks wrong. file is too small: " + self.output_path)
        if self.done:
            if self.in_place:
                if self.verbose >= 1:
                    print("deleting: " + self.input_path)
                if not self.just_print:
                    os.remove(self.input_path)
            if not self.report_start and self.verbose >= 1:
                print("[{}/{}] completed: {}".format(numerator, denominator, self.input_path))
        return self.done

audio_file_extensions = [
    ".aac",
    ".flac",
    ".mp3",
    ".m4a",
    ".ogg",
    ".wma",
    ".wav",
]
video_file_extensions = [
    ".webm",
    ".mp4",
    ".mkv",
    ".flv",
]
def main(roots, options):
    handled_files = set()
    total_files = 0
    already_audio_count = 0
    ignored_duplicate_count = 0
    video_files = []
    unrecognized_files = []
    for root in roots:
        for file_path in get_files_in(root):
            total_files += 1
            # too bad set.add doesn't return a bool like in java.
            if not (len(handled_files) < [handled_files.add(file_path), len(handled_files)][1]):
                ignored_duplicate_count += 1
                continue
            if any(file_path.endswith(ext) for ext in audio_file_extensions):
                already_audio_count += 1
                continue
            if any(file_path.endswith(ext) for ext in video_file_extensions):
                video_files.append(file_path)
                continue
            unrecognized_files.append(file_path)

    if len(unrecognized_files) > 0 and not options.ignore_unrecognized:
        sys.exit("\n".join("ERROR: unrecognized file extension: " + file_path for file_path in unrecognized_files))

    parallel_count = options.jobs
    if options.just_print:
        # just printing doesn't need to be parallelized
        parallel_count = 1
    single_file_mode = total_files == 1

    should_mkdir = None
    if options.output != None:
        if options.output.endswith(os.path.sep):
            single_file_mode = False
        if not single_file_mode:
            should_mkdir = options.output

    if should_mkdir != None:
        if not os.path.isdir(should_mkdir):
            if not options.just_print:
                os.mkdir(should_mkdir)

    # actually do it now
    active_jobs = []
    # linear progress is reported at job start
    linear_numerator = 1
    # parallel progress is reported at job completion
    parallel_numerator = 1
    denominator = len(video_files)

    def drain_some_jobs(down_to_count):
        nonlocal parallel_numerator
        while True:
            # clean up any done jobs
            for i in range(len(active_jobs) - 1, -1, -1):
                if active_jobs[i].handle_maybe_done(parallel_numerator, denominator):
                    parallel_numerator += 1
                    del active_jobs[i]
            if len(active_jobs) <= down_to_count:
                # good enough for now
                return
            os.wait()
    for file_path in video_files:
        job = Job(file_path, single_file_mode, options, parallel_count)
        active_jobs.append(job)
        job.start(linear_numerator, denominator)
        linear_numerator += 1
        if parallel_count > 0:
            drain_some_jobs(parallel_count - 1)
    drain_some_jobs(0)

    if options.verbose >= 1:
        print("")
        if ignored_duplicate_count:
            print("ignored {} duplicate files".format(ignored_duplicate_count))
        if already_audio_count:
            print("ignored {} already-audio files".format(already_audio_count))
        if len(unrecognized_files) > 0:
            print("ignored {} unrecognized files".format(len(unrecognized_files)))
        if len(video_files) > 0:
            print("converted {} video files".format(len(video_files)))

if __name__ == "__main__":
    cli()
