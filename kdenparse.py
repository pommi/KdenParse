#!/usr/bin/python3
# Copyright 2011 Will Riley
# Distributed under the terms of the GNU General Public License v3

"""
 kdenparse.py
 
 KdenParse attempts to extract and present useful information 
 from a .kdenlive XML project file.
 
 Kdenlive video editing software can be found here:
 http://www.kdenlive.org

"""
import os, sys, argparse

version_ = "%(prog)s 0.1.0"

argparser = argparse.ArgumentParser(
    prog="kdenparse.py",
    add_help=True,
    description="Parses .kdenlive project files for various metadata and timeline informations.",
)
argparser.add_argument("-V", "--version", action="version", version=version_)
argparser.add_argument(
    "--edl", action="store_true", default=False, dest="create_edl", help="Generate EDL output."
)
argparser.add_argument(
    "--deref-proxy",
    action="store_true",
    default=False,
    dest="deref_proxy",
    help="Dereference proxy clip (show original filenames)",
)
argparser.add_argument(
    "--links",
    action="store_true",
    default=False,
    dest="show_links",
    help="Show source id to filename association.",
)
argparser.add_argument(
    "--profile",
    action="store_true",
    default=False,
    dest="get_profile",
    help="Generate project profile metadata.",
)
argparser.add_argument(
    "--producers",
    action="store_true",
    default=False,
    dest="get_producers",
    help="Show MLT producers (media file) metadata.",
)
argparser.add_argument(
    "--kproducers",
    action="store_true",
    default=False,
    dest="get_kproducers",
    help="Show Kdenlive producers (media file) metadata.",
)
argparser.add_argument("projectFile")

args = argparser.parse_args()

if not os.path.isfile(args.projectFile):
    print("Not a file we can work with...")
    sys.exit(1)

try:
    args.projectFile.rindex(".kdenlive", -9)
except ValueError:
    print("Invalid filename. Exiting.")
    sys.exit(1)

from xml.dom import minidom
from decimal import Decimal, getcontext, ROUND_DOWN
from math import modf, floor
import datetime


class KdenParse:
    def __init__(self, kdenliveFile):
        self.xmldoc = minidom.parse(kdenliveFile)

    def getProjectProfile(self):
        profileDict = {}
        profile = self.xmldoc.getElementsByTagName("profile")
        keyList = profile.item(0).attributes.keys()
        for a in keyList:
            profileDict[a] = profile.item(0).attributes[a].value
        return profileDict

    def getTracks(self):
        tracks = []
        t = self.xmldoc.getElementsByTagName("track")
        for track in t:
            tracks.append(track.attributes["producer"].value)
        return tuple(tracks)

    def getPlaylists(self):
        playlistList = []
        playlists = self.xmldoc.getElementsByTagName("playlist")
        for p in playlists:
            eventList = []
            plDict = {}
            plDict["pid"] = p.attributes["id"].value
            events = p.getElementsByTagName("entry")
            for event in events:
                evDict = {}
                evDict["producer"] = event.attributes["producer"].value
                evDict["inTime"] = event.attributes["in"].value
                evDict["outTime"] = event.attributes["out"].value
                eventList.append(evDict)
            plDict["events"] = eventList
            playlistList.append(plDict)
        return tuple(playlistList)

    def getKProducers(self):
        kProducerList = []
        profile = self.xmldoc.getElementsByTagName("kdenlive_producer")
        for i in profile:
            kpDict = {}
            keyList = i.attributes.keys()
            for a in keyList:
                kpDict[i.attributes[a].name] = i.attributes[a].value
            kProducerList.append(kpDict)
        return tuple(kProducerList)

    def getProducers(self):
        producerList = []
        producers = self.xmldoc.getElementsByTagName("producer")
        for p in producers:
            pDict = {}
            pDict["pid"] = p.attributes["id"].value
            pDict["inTime"] = p.attributes["in"].value
            pDict["outTime"] = p.attributes["out"].value
            properties = p.getElementsByTagName("property")
            for props in properties:
                if props.firstChild is not None:
                    pDict[props.attributes["name"].value.replace(".", "_")] = props.firstChild.data

            producerList.append(pDict)
        return tuple(producerList)

    def linkReferences(self):
        sourceLinks = {}
        for i in self.getProducers():
            srcPid = i["pid"]
            sourceLinks[srcPid] = i["resource"]
        return sourceLinks

    def derefProxy(self):
        proxyLinks = {}
        for i in self.getKProducers():
            try:
                if i["proxy"]:
                    _proxy = i["proxy"]
                    proxyLinks[_proxy] = i["resource"]
            except KeyError:
                return False
        return proxyLinks

    def createEdl(self):
        sourceLinks = self.linkReferences()
        for playlist in self.getPlaylists():
            EdlEventCnt = 1
            progIn = datetime.datetime.strptime("00:00:00.000", '%H:%M:%S.%f')  # showtime tally
            progOut = datetime.datetime.strptime("00:00:00.000", '%H:%M:%S.%f')
            srcChannel = "C"  # default channel/track assignment
            print("\n === " + playlist["pid"] + " === \n")
            for event in playlist["events"]:
                prod = event["producer"]
                prodChunks = prod.split("_")
                srcType = prodChunks[-1].capitalize()[:1]

                # if it's an audio event, extract channel info from producer id
                if srcType == "A":
                    srcChannel = prodChunks[1]

                srcIn = datetime.datetime.strptime(event["inTime"], '%H:%M:%S.%f')  # source clip IN time
                srcOut = datetime.datetime.strptime(event["outTime"], '%H:%M:%S.%f')  # source clip OUT time
                srcDur = srcOut - srcIn
                progOut = progOut + srcDur  # increment program tally

                sourcePath = sourceLinks[prod]

                print("* FROM CLIP NAME: " + sourcePath)
                print(str(EdlEventCnt) + "  " + prod + "  ")
                print(srcType + "  " + srcChannel + "  ")
                print("{} {}".format(srcIn.strftime("%H:%M:%S.%f"), srcOut.strftime("%H:%M:%S.%f")))
                print("{} {}".format(progIn.strftime("%H:%M:%S.%f"), progOut.strftime("%H:%M:%S.%f")))

                progIn = progIn + srcDur
                EdlEventCnt = EdlEventCnt + 1


kp = KdenParse(args.projectFile)

if args.create_edl:
    kp.createEdl()

if args.get_profile:
    for i in kp.getProjectProfile().keys():
        print(i + ": " + kp.getProjectProfile()[i])

if args.get_producers:
    for i in kp.getProducers():
        print("\n=================\n")
        for kv in i:
            print(kv + ": " + i[kv])

if args.get_kproducers:
    for i in kp.getKProducers():
        print("\n=================\n")
        for kv in i:
            print(kv + ": " + i[kv])

if args.deref_proxy:
    for i in kp.derefProxy():
        print(i + ": " + kp.derefProxy()[i])

if args.show_links:
    for i in kp.linkReferences():
        print(i + ": " + kp.linkReferences()[i])
