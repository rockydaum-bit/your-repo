from dask.distributed import Client


def main() -> None:
    client = Client()  # local scheduler by default
    print(client)


if __name__ == "__main__":
    main()
