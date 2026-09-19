from solution import chunks

def check_02_chunks():
    try:
        chunks([1], 0)
    except ValueError:
        return True
    else:
        raise AssertionError("chunks args=([1], 0) got=[[1]] want=ValueError to be raised")

if __name__ == "__main__":
    check_02_chunks()
