# Example Authentise Session

- This is a very simple python example of getting an API key for an Authentise API session. 

- To test the program, you can run 
`python3 AuthSessionExample.py USER_AT_AUTHENTISE.COM PASSWORD_FOR_USER`

- To test making an order: 
`python3 MakeOrderExample.py user@email.com 'User Password!' 10x40mmtower.stl`

- To test updating an order:
` python3 UpdateOrderExample.py user@email.com 'User Password!'  "https://data.authentise.com/order/121212"`

- To test uploading a model and retrieving info about that model:
`python3 UploadAndFetchModel.py user@email.com 'User Password!' 10x40mmtower.stl 'environment' `

- (Tomer Heber) To extract stream events in an asynchronous way: `python AsyncStreamReaderLoggingExample.py --username <username> --password <password>`  (pip3 install -r requirements.txt)
