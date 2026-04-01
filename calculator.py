def add(x, y):
    return x + y

def subtract(x, y):
    return x - y

def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        return 'Error: Division by zero'
    return x / y

# Main function to handle user input and operations
def calculator():
    print('Simple Calculator')
    print('Operations: +, -, *, /')
    while True:
        try:
            num1 = float(input('Enter first number: '))
            operation = input('Enter operation (+, -, *, /): ')
            num2 = float(input('Enter second number: '))
            if operation == '+':
                print('Result:', add(num1, num2))
            elif operation == '-':
                print('Result:', subtract(num1, num2))
            elif operation == '*':
                print('Result:', multiply(num1, num2))
            elif operation == '/':
                print('Result:', divide(num1, num2))
            else:
                print('Invalid operation')
        except ValueError:
            print('Invalid input. Please enter a valid number.')
        except KeyboardInterrupt:
            print('\nExiting calculator.')
            break

# Run the calculator
calculator()