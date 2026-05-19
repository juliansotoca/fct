import sys
import glob
import os
import argparse
from src.binance_client import load_csv_transactions, fetch_all_transactions_from_api, get_client
from src.fifo_calculator import convert_all_to_eur, compute_fifo, group_by_year
from src.report_generator import create_report


def find_csv_file(data_dir="data"):
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if csv_files:
        return sorted(csv_files)[-1]
    root_csvs = glob.glob("*.csv")
    if root_csvs:
        return sorted(root_csvs)[-1]
    return None


def main():
    parser = argparse.ArgumentParser(description="Generador de informes fiscales de criptomonedas para España")
    parser.add_argument("--csv", type=str, help="Ruta al archivo CSV de transacciones de Binance")
    parser.add_argument("--api", action="store_true", help="Obtener transacciones desde la API de Binance")
    parser.add_argument("--output", type=str, default="reports", help="Directorio de salida del informe")
    parser.add_argument("--verbose", action="store_true", help="Mostrar información detallada")
    args = parser.parse_args()

    print("=" * 60)
    print("  INFORME FISCAL CRIPTOMONEDAS - ESPAÑA")
    print("  Método: FIFO | Moneda: EUR")
    print("=" * 60)
    print()

    if args.api:
        print("Conectando a la API de Binance...")
        try:
            client = get_client()
            print("Obteniendo historial de transacciones...")
            transactions = fetch_all_transactions_from_api(client)
            print(f"Transacciones obtenidas: {len(transactions)}")
        except Exception as e:
            print(f"Error al conectar con la API: {e}")
            print("Usando archivo CSV como fallback...")
            transactions = None
    else:
        transactions = None

    if not transactions:
        csv_path = args.csv or find_csv_file()
        if not csv_path:
            print("ERROR: No se encontró ningún archivo CSV.")
            print("Coloca tu CSV de Binance en el directorio 'data/' o usa --csv <ruta>")
            sys.exit(1)

        print(f"Cargando transacciones desde: {csv_path}")
        transactions = load_csv_transactions(csv_path)
        print(f"Transacciones cargadas: {len(transactions)}")

    if not transactions:
        print("ERROR: No se encontraron transacciones.")
        sys.exit(1)

    print()
    print("Convirtiendo a EUR...")
    converted = convert_all_to_eur(transactions, verbose=args.verbose)
    print("Conversión completada.")

    print()
    print("Calculando FIFO...")
    fifo_result = compute_fifo(converted)
    print(f"Disposiciones encontradas: {len(fifo_result['disposals'])}")
    print(f"Ingresos (staking, intereses...): {len(fifo_result['incomes'])}")

    print()
    print("Agrupando por año fiscal...")
    fifo_by_year = group_by_year(fifo_result)

    for year, data in sorted(fifo_by_year.items()):
        net = data["net_gain_loss"]
        print(f"  {year}: Ganancias={data['total_gains']:.2f}€ | Pérdidas={data['total_losses']:.2f}€ | Neto={net:.2f}€")

    print()
    print("Generando informe Excel...")
    output_file = create_report(fifo_by_year, inventory=fifo_result["inventory"], output_dir=args.output)
    print(f"Informe generado: {output_file}")

    print()
    print("=" * 60)
    print("  INVENTARIO ACTUAL (No vendido)")
    print("=" * 60)
    for currency, lots in sorted(fifo_result["inventory"].items()):
        if currency.upper() == "EUR":
            continue
        total_qty = sum(lot["quantity"] for lot in lots)
        total_cost = sum(lot["cost_basis"] for lot in lots)
        print(f"  {currency}: {total_qty:.8f} (coste: {total_cost:.2f}€)")

    print()
    print("=" * 60)
    print("  ¡Informe completado!")
    print("=" * 60)


if __name__ == "__main__":
    main()
