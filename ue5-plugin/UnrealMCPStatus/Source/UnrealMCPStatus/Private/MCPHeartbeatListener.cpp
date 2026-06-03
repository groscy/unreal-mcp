// Copyright unreal-mcp. Source-distributed UE5 editor plugin.

#include "MCPHeartbeatListener.h"

#include "Async/Async.h"
#include "Common/TcpSocketBuilder.h"
#include "Dom/JsonObject.h"
#include "HAL/RunnableThread.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SocketSubsystem.h"
#include "Sockets.h"

DEFINE_LOG_CATEGORY_STATIC(LogMCPStatus, Log, All);

FMCPHeartbeatListener::FMCPHeartbeatListener()
{
}

FMCPHeartbeatListener::~FMCPHeartbeatListener()
{
	Shutdown();
}

bool FMCPHeartbeatListener::Start(int32 Port)
{
	if (ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM) == nullptr)
	{
		UE_LOG(LogMCPStatus, Warning, TEXT("unreal-mcp: no socket subsystem; heartbeat listener disabled"));
		return false;
	}

	ListenSocket = FTcpSocketBuilder(TEXT("MCPHeartbeatListener"))
		.AsReusable()
		.BoundToAddress(FIPv4Address(127, 0, 0, 1))
		.BoundToPort(Port)
		.Listening(1)
		.AsNonBlocking()
		.Build();

	if (ListenSocket == nullptr)
	{
		// Most commonly the port is already in use.
		UE_LOG(LogMCPStatus, Warning,
			TEXT("unreal-mcp: could not bind heartbeat port %d (already in use?); status UI disabled"),
			Port);
		return false;
	}

	BoundPort = Port;
	bStopRequested = false;
	Thread = FRunnableThread::Create(this, TEXT("MCPHeartbeatListenerThread"), 0, TPri_BelowNormal);
	UE_LOG(LogMCPStatus, Log, TEXT("unreal-mcp: heartbeat listener bound on 127.0.0.1:%d"), Port);
	return true;
}

void FMCPHeartbeatListener::Shutdown()
{
	bStopRequested = true;

	if (Thread != nullptr)
	{
		Thread->Kill(true);
		delete Thread;
		Thread = nullptr;
	}

	if (ListenSocket != nullptr)
	{
		ListenSocket->Close();
		if (ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM))
		{
			SocketSubsystem->DestroySocket(ListenSocket);
		}
		ListenSocket = nullptr;
	}
}

uint32 FMCPHeartbeatListener::Run()
{
	while (!bStopRequested)
	{
		if (ListenSocket == nullptr)
		{
			break;
		}

		bool bHasPending = false;
		if (ListenSocket->HasPendingConnection(bHasPending) && bHasPending)
		{
			FSocket* Client = ListenSocket->Accept(TEXT("MCPHeartbeatClient"));
			if (Client != nullptr)
			{
				ServiceConnection(Client);

				Client->Close();
				if (ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM))
				{
					SocketSubsystem->DestroySocket(Client);
				}

				// The client disconnected — let the widget fall back to Stopped.
				DispatchEvent(TEXT("closed"), 0);
			}
		}

		// Poll interval for new connections; cheap and responsive enough.
		FPlatformProcess::Sleep(0.1f);
	}

	return 0;
}

void FMCPHeartbeatListener::ServiceConnection(FSocket* Client)
{
	FString Buffer;
	uint8 Chunk[1024];

	while (!bStopRequested)
	{
		// Block briefly for readability so we don't spin the CPU.
		if (!Client->Wait(ESocketWaitConditions::WaitForRead, FTimespan::FromMilliseconds(200)))
		{
			// Timed out with no data; check connection liveness and loop.
			if (Client->GetConnectionState() == SCS_ConnectionError)
			{
				return;
			}
			continue;
		}

		int32 BytesRead = 0;
		if (!Client->Recv(Chunk, sizeof(Chunk), BytesRead))
		{
			// Recv failed — treat as closed.
			return;
		}

		if (BytesRead <= 0)
		{
			// Graceful close (EOF).
			return;
		}

		Buffer.Append(FString(BytesRead, reinterpret_cast<ANSICHAR*>(Chunk)));

		// Extract complete newline-delimited lines.
		int32 NewlineIndex = INDEX_NONE;
		while (Buffer.FindChar(TEXT('\n'), NewlineIndex))
		{
			FString Line = Buffer.Left(NewlineIndex);
			Buffer.RightChopInline(NewlineIndex + 1);
			Line.TrimStartAndEndInline();
			if (!Line.IsEmpty())
			{
				HandleLine(Line);
			}
		}
	}
}

void FMCPHeartbeatListener::HandleLine(const FString& Line)
{
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Line);
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		UE_LOG(LogMCPStatus, Verbose, TEXT("unreal-mcp: ignoring malformed heartbeat line: %s"), *Line);
		return;
	}

	const FString EventType = JsonObject->GetStringField(TEXT("event"));
	int32 Pid = 0;
	JsonObject->TryGetNumberField(TEXT("pid"), Pid);

	if (!EventType.IsEmpty())
	{
		DispatchEvent(EventType, Pid);
	}
}

void FMCPHeartbeatListener::DispatchEvent(const FString& EventType, int32 Pid)
{
	// Marshal onto the game thread so delegate handlers can touch Slate safely.
	FOnMCPEventReceived DelegateCopy = OnEventReceived;
	AsyncTask(ENamedThreads::GameThread, [DelegateCopy, EventType, Pid]()
	{
		DelegateCopy.ExecuteIfBound(EventType, Pid);
	});
}
