#!/usr/bin/env python3
"""Shared map: video_id -> ASR-difficulty category, from the team's labeled
videos_dataset/ (folders = human difficulty ratings). Categories are disjoint."""
import glob, os
DATASET = os.environ.get("VIDEOS_DATASET", "/Users/savayan/Documents/videos_dataset")
CATS = ["single_speaker","formal","multi_speakers","difficult","songs","songs_difficult"]
# rough "harder ->" ordering for display
ORDER = ["formal","single_speaker","multi_speakers","songs","difficult","songs_difficult"]

def video_to_category(dataset=DATASET):
    m = {}
    for d in CATS:
        for f in glob.glob(os.path.join(dataset, d, "*.mp4")):
            m.setdefault(os.path.basename(f)[:-4], d)
    return m

if __name__ == "__main__":
    m = video_to_category()
    from collections import Counter
    print(f"{len(m)} videos labeled; per category:", dict(Counter(m.values())))
