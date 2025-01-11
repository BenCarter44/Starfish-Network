# Starfish OS demo

Brief overview of repository:
- The programs that can be executed on the OS are found in `/examples`
- The code for the OS is in `/src`
<br>
So, to see the OS in action, start up the OS on multiple nodes and
watch it execute several programs from the `/examples` directory.
<br>
<br>
If you want to run your own program on the OS, just make another file in `/examples` that 
follows the STAR framework (see the existing programs, it's pretty simple) and "compile it". Then, run `simple_executor.py <PATH TO STAR PROGRAM>` to run a STAR program.

# Running the pre-written example programs

1. Setup environment
``` bash
virtualenv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2. "Compile" example programs
``` bash
cd examples
python3 sample.stardef.py
python3 list_dist.stardef.py
python3 file_reader.stardef.py
cd ../
```
3. Start up the operating system.<br>
    __In FOUR terminals:__
    
    ``` bash
     # Terminal 1
     python3 test2.py 1
    ```
    ``` bash
     # Terminal 2
     python3 test2.py 2
    ```
    ``` bash
     # Terminal 3
     python3 test2.py 3
    ```
    ``` bash
     # Terminal 4
     python3 test2.py 4
    ```

4. Watch it run!

# Running a custom program

1. Make sure the steps for the pre-written programs are working correctly.
2. Create a program using the STAR framework. See [STAR_FRAMEWORK.md](/docs/STAR_FRAMEWORK.md) for info.
3. Compile the program (by executing the python program directly. See STAR_FRAMEWORK.md and the `#Compiling` section for more details.)
4. Run `simple_executor.py <PATH TO STAR PROGRAM>` to run a STAR program

