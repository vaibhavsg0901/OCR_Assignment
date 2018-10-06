#!/usr/bin/python3

import cv2
import numpy as np
import sys
import os.path
import pytesseract
from PIL import Image
import argparse

parser = argparse.ArgumentParser(description = "OCR")
parser.add_argument("input_file", help = "Image document")
args = parser.parse_args()
input_file = args.input_file
output_file = "input.jpg"
	
if not os.path.isfile(input_file):
    print ("No such file '%s'" % input_file)
    sys.exit()

DEBUG = 0

def ii(xx, yy):
    global img, img_y, img_x
    if yy >= img_y or xx >= img_x:
        return 0
    pixel = img[yy][xx]
    return 0.30 * pixel[2] + 0.59 * pixel[1] + 0.11 * pixel[0]

def connected(contour):
    first = contour[0][0]
    last = contour[len(contour) - 1][0]
    return abs(first[0] - last[0]) <= 1 and abs(first[1] - last[1]) <= 1

def c(index):
    global contours
    return contours[index]

def count_children(index, h_, contour):
	if h_[index][2] < 0:
		return 0
	else:
		if keep(c(h_[index][2])):
			count = 1
		else:
			count = 0

		count += count_siblings(h_[index][2], h_, contour, True)
		return count

def is_child(index, h_):
    return get_parent(index, h_) > 0

def get_parent(index, h_):
    parent = h_[index][3]
    while not keep(c(parent)) and parent > 0:
        parent = h_[parent][3]

    return parent

def count_siblings(index, h_, contour, inc_children=False):
    if inc_children:
        count = count_children(index, h_, contour)
    else:
        count = 0

    p_ = h_[index][0]
    while p_ > 0:
        if keep(c(p_)):
            count += 1
        if inc_children:
            count += count_children(p_, h_, contour)
        p_ = h_[p_][0]

   
    n = h_[index][1]
    while n > 0:
        if keep(c(n)):
            count += 1
        if inc_children:
            count += count_children(n, h_, contour)
        n = h_[n][1]
    return count

def keep(contour):
    return keep_box(contour) and connected(contour)

def keep_box(contour):
    xx, yy, w_, h_ = cv2.boundingRect(contour)

    w_ *= 1.0
    h_ *= 1.0

    if w_ / h_ < 0.1 or w_ / h_ > 10:
        if DEBUG:
            print ("\t Rejected because of shape: (" + str(xx) + "," + str(yy) + "," + str(w_) + "," + str(h_) + ")" + \
                  str(w_ / h_))
        return False
    
    if ((w_ * h_) > ((img_x * img_y) / 5)) or ((w_ * h_) < 15):
        if DEBUG:
            print ("\t Rejected because of size")
        return False

    return True


def include_box(index, h_, contour):
    if DEBUG:
        print (str(index) + ":")
        if is_child(index, h_):
            print ("\tIs a child")
            print ("\tparent " + str(get_parent(index, h_)) + " has " + str(
                count_children(get_parent(index, h_), h_, contour)) + " children")
            print ("\thas " + str(count_children(index, h_, contour)) + " children")

    if is_child(index, h_) and count_children(get_parent(index, h_), h_, contour) <= 2:
        if DEBUG:
            print ("\t skipping: is an interior to a letter")
        return False

    if count_children(index, h_, contour) > 2:
        if DEBUG:
            print ("\t skipping, is a container of letters")
        return False

    if DEBUG:
        print ("\t keeping")
    return True

orig_img = cv2.imread(input_file)

img = cv2.copyMakeBorder(orig_img, 50, 50, 50, 50, cv2.BORDER_CONSTANT)
img_y = len(img)
img_x = len(img[0])

if DEBUG:
    print ("Image is " + str(len(img)) + "x" + str(len(img[0])))

blue, green, red = cv2.split(img)

blue_edges = cv2.Canny(blue, 200, 250)
green_edges = cv2.Canny(green, 200, 250)
red_edges = cv2.Canny(red, 200, 250)

edges = blue_edges | green_edges | red_edges

other, contours, hierarchy = cv2.findContours(edges.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

hierarchy = hierarchy[0]

if DEBUG:
    processed = edges.copy()
    rejected = edges.copy()

keepers = []

for index_, contour_ in enumerate(contours):
    if DEBUG:
        print ("Processing #%d" % index_)

    x, y, w, h = cv2.boundingRect(contour_)
    if keep(contour_) and include_box(index_, hierarchy, contour_):
        keepers.append([contour_, [x, y, w, h]])
        if DEBUG:
            cv2.rectangle(processed, (x, y), (x + w, y + h), (100, 100, 100), 1)
            cv2.putText(processed, str(index_), (x, y - 5), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 255))
    else:
        if DEBUG:
            cv2.rectangle(rejected, (x, y), (x + w, y + h), (100, 100, 100), 1)
            cv2.putText(rejected, str(index_), (x, y - 5), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 255))

new_image = edges.copy()
new_image.fill(255)
boxes = []

for index_, (contour_, box) in enumerate(keepers):
    fg_int = 0.0
    for p in contour_:
        fg_int += ii(p[0][0], p[0][1])

    fg_int /= len(contour_)
    if DEBUG:
        print ("FG Intensity for #%d = %d" % (index_, fg_int))
    x_, y_, width, height = box
    bg_int = \
        [
            ii(x_ - 1, y_ - 1),
            ii(x_ - 1, y_),
            ii(x_, y_ - 1),

            ii(x_ + width + 1, y_ - 1),
            ii(x_ + width, y_ - 1),
            ii(x_ + width + 1, y_),

            ii(x_ - 1, y_ + height + 1),
            ii(x_ - 1, y_ + height),
            ii(x_, y_ + height + 1),

            ii(x_ + width + 1, y_ + height + 1),
            ii(x_ + width, y_ + height + 1),
            ii(x_ + width + 1, y_ + height)
        ]
        
    bg_int = np.median(bg_int)

    if DEBUG:
        print ("BG Intensity for #%d = %s" % (index_, repr(bg_int)))

    if fg_int >= bg_int:
        fg = 255
        bg = 0
    else:
        fg = 0
        bg = 255
        
    for x in range(x_, x_ + width):
        for y in range(y_, y_ + height):
            if y >= img_y or x >= img_x:
                if DEBUG:
                    print ("pixel out of bounds (%d,%d)" % (y, x))
                continue
            if ii(x, y) > fg_int:
                new_image[y][x] = bg
            else:
                new_image[y][x] = fg

new_image = cv2.blur(new_image, (2, 2))
cv2.imwrite(output_file, new_image)
if DEBUG:
    cv2.imwrite('edges.png', edges)
    cv2.imwrite('processed.png', processed)
    cv2.imwrite('rejected.png', rejected)

print(pytesseract.image_to_string(Image.open("input.jpg")))
os.remove("input.jpg")       

