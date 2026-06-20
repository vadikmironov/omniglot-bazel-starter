use reqwest::StatusCode;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let resp = reqwest::get("http://info.cern.ch/").await?;
    let status_code = resp.status();

    println!("HTTP status code = {status_code}");

    if status_code == StatusCode::OK {
        let text = resp.text().await?;
        println!("\n+++++ HTML content +++++\n");
        println!("{}", august::convert(&text, 80));

        Ok(())
    } else {
        Err("HTTP request failed with status code {status_code}".into())
    }
}
