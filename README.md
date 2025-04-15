![Header](https://codingcando.com/blog/media/f83e22273905f19e882eab3667f6a7c9267ff135848b62c9450f4e7c1d2771c7.jpeg)

# Starfish OS
A highly tolerant distributed network! Like a Starfish: No central brain, cut it in half, it stays alive! Rethinking distributed computing. Welcome to the Starfish-Network

Creating a "virtualized computer" that can run on hundreds of nodes, with the nodes constantly going in and out. This virtualized computer has highly tolerant storage, can execute processes, and has I/O. This also will be completely decentralized, as opposed to a common technique of having a "master" server. All nodes are "treated the same"

Imagine a table with one hundred table legs. Now, imagine those table legs randomly appearing and disappearing. Will the table stay standing? This network seeks to make this possible, make a sturdy execution/storage environment highly tolerant of individual nodes coming and leaving.

---

This is currently a research project for [Benjamin Carter's](https://codingcando.com/) undergraduate capstone under the direction of Professor [Dr. Isac Artzi](https://www.gcu.edu/faculty-list) and with a research advisor of Professor [David Demland](https://www.gcu.edu/faculty-list) at Grand Canyon University.

---

[Watch a video of a OS visual that demonstrates node communication in real time here.](https://codingcando.com/fileShare/file?code=CD2KBNHH23)

[See a demo of StarfishOS in action (no sound)](https://codingcando.com/fileShare/file?code=starfishUse)

[View my research poster here.](https://codingcando.com/fileShare/file?code=starfishOS)

This project was presented in front of Grand Canyon University Administration, including the Provost and President of the University, in the GCU Undergraduate Research Symposium. [See the news article.](https://news.gcu.edu/gcu-news/students-highlight-unique-studies-at-research-symposium/)

---

## Overview - In Simple English

A simple lay-man definition of a computer is this: A machine that:
- Can execute stuff (Execution Environment)
- Can store stuff (Persistent Storage)
- Has input and output. (IO)

So, the Starfish Network seeks to recreate the above, to "simulate a computer".

- A Distributed CPU-like platform
- A Distributed Persistent Storage (Virtual Disk/File System)
- A Distributed Approach to IO

It seeks to combine those into one unified system. A completely distributed OS.

This repository is a proof of concept of the Starfish OS and architecture. A node can be run as a Docker container by building the
provided Dockerfile. 

See the `/docs/general.md` for more information. Or, [take a look at the overview blog article](https://codingcando.com/starfish)

## For demo and more info, see the `/docs` folder
