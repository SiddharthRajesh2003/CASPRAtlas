import pandas as pd
import subprocess
import time
import os
from subprocess import CalledProcessError

# Path to Cygwin bash.exe - VERIFY THIS PATH
CYGWIN_BASH = r"C:\cygwin64\bin\bash.exe"
EDIRECT_PATH = "/home/siddh/edirect"  # Cygwin path to edirect tools

def get_apa_citation_for_pmid(pmid):
    """
    Uses NCBI's pma2apa script in Cygwin with proper environment setup
    """
    try:
        # Critical fix: Use interactive login shell and source profile
        bash_command = f'''
            source ~/.bash_profile
            source ~/.bashrc
            export PATH="$PATH:{EDIRECT_PATH}"
            {EDIRECT_PATH}/efetch -db pubmed -id {pmid} -format xml | 
            {EDIRECT_PATH}/pma2apa
        '''
        
        # Run with proper environment setup
        result = subprocess.run(
            [CYGWIN_BASH, '-i', '-l', '-c', bash_command],
            capture_output=True,
            text=True,
            check=True  # Raise error on failure
        )
        
        return result.stdout.strip()

    except CalledProcessError as e:
        error_msg = f"Bash error [{e.returncode}]: {e.stderr.strip()}"
        return error_msg
    except Exception as e:
        return f"General error: {str(e)}"

def process_pmid_list(input_file, output_file):
    """
    Processes PMID list with enhanced error checking
    """
    try:
        # Verify critical paths exist
        if not os.path.exists(CYGWIN_BASH):
            raise FileNotFoundError(f"Cygwin bash not found at {CYGWIN_BASH}")
            
        # Test edirect installation through Cygwin
        test_cmd = f'''
            source ~/.bash_profile
            test -f {EDIRECT_PATH}/efetch && 
            test -f {EDIRECT_PATH}/pma2apa && 
            echo "OK"
        '''
        test_result = subprocess.run(
            [CYGWIN_BASH, '-i', '-l', '-c', test_cmd],
            capture_output=True,
            text=True
        )
        
        if "OK" not in test_result.stdout:
            raise EnvironmentError(
                f"Edirect tools missing. Check installation in {EDIRECT_PATH}\n"
                f"Test output: {test_result.stderr}"
            )

        # Read PMIDs
        df = pd.read_excel(input_file)
        pmid_column = df.columns[0]
        pmids = df[pmid_column].astype(str).tolist()

        citations = []
        total = len(pmids)
        print(f"Processing {total} PMIDs...")

        for i, pmid in enumerate(pmids):
            if not pmid.strip().isdigit():
                citations.append({"PMID": pmid, "APA Citation": "Invalid PMID format"})
                continue

            citation = get_apa_citation_for_pmid(pmid.strip())
            citations.append({"PMID": pmid, "APA Citation": citation})

            # Progress reporting
            if (i + 1) % 10 == 0 or i == total - 1:
                print(f"Processed {i + 1}/{total} ({((i+1)/total)*100:.1f}%)")
            
            time.sleep(0.33)  # NCBI rate limit compliance

        # Save results
        result_df = pd.DataFrame(citations)
        result_df.to_excel(output_file, index=False)
        print(f"Success! Output saved to {output_file}")
        return True

    except Exception as e:
        print(f"Fatal error: {str(e)}")
        return False

if __name__ == "__main__":
    # Use raw strings for Windows paths
    input_file = "Citations.xlsx"  
    output_file = "pmid_citations.xlsx"
    
    process_pmid_list(input_file, output_file)