#!/usr/bin/env python3

import sys
from getopt import getopt, GetoptError
import os
import os.path
import shutil
import math
#import ffmpeg
import subprocess

EXTENSION = '.mp4'

def usage():
	print("audi-ffmpeg.py - Convert Video files to a format suitable for Audi MMI 3G")
	print("")
	print("  Usages:")
	print("    audi-ffmpeg.py [-h, --help]")
	print("    audi-ffmpeg.py [options] -a [<input> [<output>]]")
	print("    audi-ffmpeg.py [options] <input> <output>")
	print("")
	print("  Options:")
	print("    -h, --help")
	print("    -v, --verbose")
	print("    -a, --all")
	print("    -d, --dryrun")
	print("    --width <width>")
	print("    --height <height>")

def convert_one(width: int, height: int, input: str, output: str, verbose: bool, dryrun: bool):
	if verbose:
		print("Converting \"{0}\" to \"{1}\"".format(input, output))
	try:
		cropdetect_command = ["ffmpeg", "-hide_banner", "-i", input, "-vf", "cropdetect", "-f", "null", "-"]
		if verbose:
			print("Executing cropdetect {0}".format(cropdetect_command))
		cropdetect_completion = subprocess.run(cropdetect_command, capture_output=True, check=True)
	except subprocess.CalledProcessError as e:
		print(e.stderr.decode(), file=sys.stderr)
		sys.exit(1)

#	try:
#		out, err = (
#			ffmpeg
#			.input(input)
#			.filter('cropdetect')
#			.output('-', format='null')
#			.global_args('-hide_banner')
#			.run(quiet=True)
#		)
#	except ffmpeg.Error as e:
#		print(e.stderr.decode(), file=sys.stderr)
#		sys.exit(1)
# Cropping input to 1408:1072:252:4, Scaling output to 632:480
# Skipped executing "['ffmpeg', '-i', './sabotage.mp4', '-filter_complex', '[0]crop=1408:1072:252:4[s0];[s0]scale=632:480[s1]', '-map', '[s1]', '-f', 'mp4', './resized/sabotage.mp4', '-y', '-hide_banner']"
	
	cropdetect_lines = cropdetect_completion.stderr.splitlines(True)
	cropdetect_line = cropdetect_lines[-3]
	cropdetect_split = str(cropdetect_line, 'utf-8').split('crop=')
	cropdetect_string = cropdetect_split[-1].strip('\n')
	crop_elements = cropdetect_string.split(':')
	crop_width = crop_elements[0]
	crop_height = crop_elements[1]
	crop_x = crop_elements[2]
	crop_y = crop_elements[3]

	# Calculate the scale to use to ensure either the height or width fits in the
	# given output size
	scale = min(float(width) / float(crop_width), float(height) / float(crop_height))
	# Calculate the output video width/height and ensure is an even number
	# so that ffmpeg filters don't break
	video_height = math.ceil(scale * float(crop_height) / 2.) * 2
	video_width = math.ceil(scale * float(crop_width) / 2.) * 2

	# If the video size is larger than output size, then go with output size.
	if video_width > width:
		video_width = width
	if video_height > height:
		video_height = height

	# If the crop size is smaller than video size, then go with crop size.
	if int(crop_width) < video_width:
		video_width = int(crop_width)
	if int(crop_height) < video_height:
		video_height = int(crop_height)

	if verbose:
		print("Cropping input to {0}:{1}:{2}:{3}, Scaling output to {4}:{5}".format(crop_width, crop_height, crop_x, crop_y, video_width, video_height))
	
	try:
		resize_command = ["ffmpeg", "-hide_banner",
		    "-i", input,
#			"-vf", "crop={0}:{1}:{2}:{3}".format(crop_width, crop_height, crop_x, crop_y),
#			"-vf", "scale={0}:{1}".format(video_width, video_height),
			"-filter_complex",
			"crop={0}:{1}:{2}:{3},scale={4}:{5}".format(crop_width, crop_height, crop_x, crop_y, video_width, video_height),
			"-f", "mp4",
			"-y", output]
		if dryrun:
			print("Skipped executing \"{0}\"".format(resize_command))
		else:
			if verbose:
				print("Executing resize \"{0}\"".format(resize_command))
			resize_completion = subprocess.run(resize_command, capture_output=True, check=True)
	except subprocess.CalledProcessError as e:
		print(e.stderr.decode(), file=sys.stderr)
		sys.exit(1)

#	try:
#		stream = (
#			ffmpeg
#			.input(input)
#			.crop(crop_x, crop_y, crop_width, crop_height)
#			.filter('scale', video_width, video_height)
#			.output(output, format='mp4')
#			.overwrite_output()
#			.global_args('-hide_banner')
#		)
#
#		if dryrun:
#			command = stream.compile()
#		else:
#			out, err = stream.run(quiet=True)
#	except ffmpeg.Error as e:
#		print(e.stderr.decode(), file=sys.stderr)
#		sys.exit(1)
	
def convert_all(width: int, height: int, input: str, output: str, verbose: bool, dryrun: bool):
	if verbose:
		print("Converting all the files with extension {0} in directory \"{1}\" to directory \"{2}\"".format(EXTENSION, input, output))
	if os.path.exists(output):
		if verbose:
			print("Deleting directory \"{0}\"".format(output))
		if dryrun:
			print("Skipped deleting directory \"{0}\"".format(output))
		else:
			shutil.rmtree(output)
	
	if dryrun:
		print("Skipped creating directory \"{0}\"".format(output))
	else:
		os.mkdir(output)
	
	for entry in os.scandir(input):
		if entry.is_file() and entry.name.endswith(EXTENSION):
			file_input = os.path.join(input, entry.name)
			file_output = os.path.join(output, entry.name)
			convert_one(width, height, file_input, file_output, verbose, dryrun)

def main(argv):
	if len(argv) == 0:
		usage()
		sys.exit(2)
	
	try:
		opts, args = getopt(argv, 'hvad', ['help', 'verbose', 'all', 'dryrun', 'width=', 'height='])
	except GetoptError:
		usage()
		sys.exit(2)
	
	all: bool = False
	verbose: bool = False
	dryrun: bool = False
	width: int=720
	height: int=480
	input: str=None
	output: str=None

	for opt, arg in opts:
		if opt in ('-h', '--help'):
			usage()
			sys.exit()
		if opt in ('-v', '--verbose'):
			verbose = True
		if opt in ('-d', '--dryrun'):
			dryrun = True
		elif opt in ('-a', '--all'):
			all = True
			if input is None:
				input = "."
			if output is None:
				output = os.path.join(input, "resized")
		elif opt in ('--width'):
			width = int(arg)
		elif opt in ('--height'):
			height = int(arg)
	
	if len(args) > 0:
		input = args[0]
	if len(args) > 1:
		output = args[1]

	if input is None or output is None:
		usage()
		sys.exit(2)

	if verbose:
		print("all={0},width={1},height={2},input={3},output={4}".format(all, width, height, input, output))

	if all:
		convert_all(width, height, input, output, verbose, dryrun)
	else:
		convert_one(width, height, input, output, verbose, dryrun)

	sys.exit(0)

if __name__ == '__main__':
	main(sys.argv[1:])
