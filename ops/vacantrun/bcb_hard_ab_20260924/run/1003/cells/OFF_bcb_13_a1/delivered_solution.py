import subprocess
import ftplib
import os

def task_func(ftp_server='ftp.dlptest.com', ftp_user='dlpuser', ftp_password='rNrKYTX9g7z3RgJRmxWuGHbeu', ftp_dir='/ftp/test'):
    filenames = []
    try:
        # Connect to the FTP server
        try:
            ftp = ftplib.FTP(ftp_server)
        except Exception as e:
            raise Exception(f"Failed to connect to FTP server {ftp_server}: {str(e)}")

        # Log into the FTP server
        try:
            ftp.login(user=ftp_user, passwd=ftp_password)
        except Exception as e:
            raise Exception(f"Failed to log into FTP server {ftp_server} with user {ftp_user}: {str(e)}")

        # Change to the specified directory
        try:
            ftp.cwd(ftp_dir)
        except Exception as e:
            raise Exception(f"Failed to change to directory {ftp_dir} on server {ftp_server}: {str(e)}")

        # List files in the directory
        files = ftp.nlst()
        filenames = files

        # Download each file using wget
        for filename in filenames:
            current_path = ftp.pwd()
            base_path = current_path.rstrip('/')
            if not base_path: # Root directory
                url = f"ftp://{ftp_server}/{filename}"
            else:
                if base_path.startswith('/'):
                    url = f"ftp://{ftp_server}{base_path}/{filename}"
                else:
                    url = f"ftp://{ftp_server}/{base_path}/{filename}"
            
            # Use subprocess to run wget
            subprocess.run([
                'wget', 
                f'--ftp-user={ftp_user}', 
                f'--ftp-password={ftp_password}', 
                url
            ], check=True, capture_output=True)

        ftp.quit()
    except Exception as e:
        if str(e).startswith("Failed to"):
            raise e
        # If it's not one of our custom exceptions, we should still raise it 
        # unless the goal says otherwise. The goal doesn't say what to do with other errors.
        # However, if wget fails, subprocess.run(check=True) will raise CalledProcessError.
        raise e

    return filenames
