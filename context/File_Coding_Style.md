## This file tells how should each comment, variable and function be defined and structured. You must follow this format for all the functions, variables and comments

I am using Python language as an example for class, function, variable and comment definition.

```
{There must be two line gap before the function/class definition}

# ROLE: {You write the role of the function - what is this function doing in one line}
def/async def {function_name}({parameter_name}: {data_type}) -> {return_type (optional but preferred)}:
    ''' {Docstring should be short and sweet and must convey complete meaning} '''
    {A new line after the doc string}
    # FLOW-1: {You must define the flow of the function here - like - statement-1 define abc}
    statement-1     # USE: {You must write the use of the statements in the function (only write the important or not so common ones, not every)}
    {A new line after statement-1}
    # FLOW-2: {The flow should continue like - abc is used to do xyz in statement-2}
    statement-2
    {There must not be a new line before the loop. If the statement before it is connected to the loop then there must not be a new line. If not and the loop is a standalone loop then there must be}
    # FLOW-3: ...
    for a in b:
        statement-3 
    {There must be a new line after ending any loop. Loops end and the next statement should not be continuous}

    return abc     {Return statement or print statement should be in a separate line}


{There must be two line gap after the function/class definition}
```

### Additional Rules
1. You must write simple functions and not too complex functions
2. If the functions are going to be complex then you must make it look simple. Structure it so that it is not overwhelming to read.
3. Try to make all the functions look simple.
4. You must not overcomplicate/over-engineer things while creating functions
5. Make sure that the function shouldn't look crowded or messy.
6. Make sure to not use emojis
7. Do the same for classes also
8. The flow should feel connected like statement-1 was liquid so statement-2 should be water. You must comment in such a way that it reveals how statement-1 and statement-2 are connected. The flow you write must connect the actual sense of the two statements or logics.

## Rule for variables and file's internal structure

```
# WHAT DOES THIS FILE DO: {Give the meaning of creating this file in one line in Human English.}
{Leave a line}
# ================== IMPORTS ==================
from abc import xyz
...
{You must keep the third party-imports separated by a line from folder-related imports}
# ================== IMPORTS ==================

{leave two lines}
# =========== VARIABLES : {What are these variables for? Or Where are these variables gonna be used? Or Some common category for these variables} ===========
a = 1
b = 2
...
# =========== VARIABLES : {What are these variables for? Or Where are these variables gonna be used? Or Some common category for these variables} ===========

{leave two lines}
# =========== FUNCTION ===========
# ROLE: ...
def...
# =========== FUNCTION ===========

# =========== CLASS ===========
# ROLE: ...
class {class_name}:
    {leave one line}
    # =========== FUNCTION ===========
    def ...
    # =========== FUNCTION ===========
# =========== CLASS ===========
```

### Additional Rules
1. The file's coding structure should be very neat and clean
2. Make sure the comments doesn't look like AI Generated Comments. Do not write comments in perfect english flow and grammar. It should be written in a human language and humans do not write perfect english grammar or perfect logic flow. Their english is understandable but not perfect like I am writing now.
3. Make sure that the file doesn't look messy or crowded. Give proper lines
4. Make sure to not use emojis