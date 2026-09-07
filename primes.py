def is_prime(n):
    """Check if a number is prime."""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


def primes_less_than(x):
    """Return a list of prime numbers less than x."""
    return [i for i in range(2, x) if is_prime(i)]


def main():
    try:
        x = int(input("Enter a number (x): "))
        if x < 2:
            print("No prime numbers less than", x)
            return
        primes = primes_less_than(x)
        print(f"Prime numbers less than {x}:")
        print(primes)
        print(f"Total: {len(primes)} primes found")
    except ValueError:
        print("Please enter a valid integer.")


if __name__ == "__main__":
    main()