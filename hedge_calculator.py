from dataclasses import dataclass


@dataclass
class Position:
    size: float
    avg_price: float


def add_order(position: Position, add_size: float, price: float):
    total_value = position.size * position.avg_price
    total_value += add_size * price
    new_size = position.size + add_size
    new_avg = total_value / new_size
    return Position(new_size, new_avg)


def calc_profit_price(long: Position, short: Position, target=1.0):
    # long.size*(P - long.avg) + short.size*(short.avg - P) = target

    A = long.size - short.size
    B = short.size * short.avg_price - long.size * long.avg_price

    if A == 0:
        return None

    P = (target - B) / A
    return P


def print_state(step, long, short, target_price):
    print("\n" + "=" * 50)
    print(f"ШАГ {step}")
    print(f"LONG  size={long.size:.4f}  avg={long.avg_price:.5f}")
    print(f"SHORT size={short.size:.4f}  avg={short.avg_price:.5f}")

    if target_price:
        print(f"Точка +1$ = {target_price:.5f}")
    else:
        print("Невозможно вычислить (баланс LONG=SHORT)")
    print("=" * 50)


def run_simulator():

    print("=== HEDGE CONFIG CALCULATOR ===")

    # старт
    long_size = float(input("START LONG size: "))
    long_price = float(input("START LONG price: "))
    short_size = float(input("START SHORT size: "))
    short_price = float(input("START SHORT price: "))

    main_multiplier = float(input("Main multiplier (например 2 или 3): "))
    opposite_multiplier = float(input("Opposite multiplier (например 0.25, 0.5, 0.75): "))

    target_profit = float(input("Target profit (например 1): "))

    long = Position(long_size, long_price)
    short = Position(short_size, short_price)

    step = 0
    print_state(step, long, short, calc_profit_price(long, short, target_profit))

    while True:
        step += 1
        signal = input("\nВведите сигнал (LONG/SHORT) или 'exit': ").upper()

        if signal == "EXIT":
            break

        price = float(input("Введите цену сигнала: "))

        if signal == "LONG":
            long = add_order(long, long.size * main_multiplier, price)
            short = add_order(short, short.size * opposite_multiplier, price)

        elif signal == "SHORT":
            short = add_order(short, short.size * main_multiplier, price)
            long = add_order(long, long.size * opposite_multiplier, price)

        else:
            print("Неверный ввод")
            step -= 1
            continue

        target_price = calc_profit_price(long, short, target_profit)
        print_state(step, long, short, target_price)


if __name__ == "__main__":
    run_simulator()