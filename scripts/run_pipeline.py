import subprocess
import sys
import os

def run_script(script_path):
    """
    Executes a given Python script using the same Python interpreter
    that is running this script (i.e., the one from your venv).
    It will stop and report an error if the script fails.
    """
    try:
        # sys.executable ensures we use the python from our virtual environment.
        # check=True will raise an error if the script returns a non-zero exit code.
        subprocess.run([sys.executable, script_path], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running script: {script_path}")
        print(f"Return code: {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"Error: Script not found at '{script_path}'")
        return False

def main():
    """
    Runs the full data update and model training pipeline in the correct order.
    """
    print("--- Starting Full Data and Model Update Pipeline ---")
    
    # Get the directory where this script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the sequence of scripts to run.
    pipeline_scripts = [
        os.path.join(script_dir, "update_data.py"),
        os.path.join(script_dir, "prepare_team_stats.py"),
        os.path.join(script_dir, "train_model.py")
    ]
    
    for i, script in enumerate(pipeline_scripts):
        print(f"\n[Step {i+1}/{len(pipeline_scripts)}] Executing '{os.path.basename(script)}'...")
        
        # If any script in the sequence fails, we stop the whole pipeline.
        if not run_script(script):
            print("\n--- Pipeline failed at this step. Aborting. ---")
            return
            
    print("\n--- Full Pipeline Completed Successfully! ---")
    print("Your data is updated, stats are processed, and the model is retrained.")

if __name__ == "__main__":
    main()
