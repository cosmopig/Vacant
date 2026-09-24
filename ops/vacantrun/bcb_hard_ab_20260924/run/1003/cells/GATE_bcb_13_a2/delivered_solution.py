import subprocess
import ftplib
import os

def task_func(ftp_server='ftp.dlptest.com', ftp_user='dlpuser', ftp_password='rNrKYTX9g7z3RgJRmxWuGHbeu', ftp_dir='/ftp/test'):
    try:
        ftp = ftplib.FTP(ftp_server)
    except Exception as e:
        raise Exception(f"Failed to connect to FTP server {ftp_server}: {str(e)}")

    try:
        ftp.login(user=ftp_user, passwd=ftp_password)
    except Exception as e:
        try:
            ftp.quit()
        except:
            pass
        raise Exception(f"Failed to log into FTP server {ftp_server} with user {ftp_user}: {str(e)}")

    try:
        ftp.cwd(ftp_dir)
    except Exception as e:
        try:
            ftp.quit()
        except:
            pass
        raise Exception(f"Failed to change to directory {ftp_dir} on server {ftp_server}: {str(e)}")

    filenames = ftp.nlst()
    attempted_files = []
    
    for filename in filenames:
        if filename in ('.', '..'):
            continue
        attempted_files.append(filename)
        
        path = ftp_dir.lstrip('/')
        if path == '':
            base_url = f"ftp://{ftp_server}/"
        else:
            base_url = f"ftp://{ftp_server}/{path}/"
        
        url = base_url + filename
        
        try:
            subprocess.run(
                ['wget', '--ftp-user=' + ftp_user, '--ftp-password=' + ftp_password, url],
                capture_output=True,
                check=False
            )
        except Exception:
            pass

    try:
        ftp.quit()
    except:
        pass
        
    return attempted_files
